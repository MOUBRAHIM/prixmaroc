"""
Modération des prix communautaires du souk.

Objectif : filtrer les soumissions aberrantes ou frauduleuses AVANT publication,
sans friction pour l'utilisateur honnête.

Stratégie en cascade (robuste même sans crédit IA) :
  1. Garde-fous absolus        → rejet immédiat (prix négatif / délirant)
  2. Fourchette par catégorie  → bon sens marché marocain (MAD/kg)
  3. Comparaison à la médiane   → écart vs relevés récents du même produit/ville
  4. Renfort Claude (optionnel) → tranche les cas douteux, sinon on garde l'étape 3
"""
from __future__ import annotations

import logging
import statistics
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.souk_price import SoukCategory, SoukPrice, SoukStatus

logger = logging.getLogger(__name__)

# Fourchettes de bon sens en MAD/kg (marché marocain 2026) — larges volontairement.
# Utilisées seulement quand l'unité est le kilo.
_SANITY_KG: dict[SoukCategory, tuple[float, float]] = {
    SoukCategory.LEGUMES: (1.0, 60.0),
    SoukCategory.FRUITS:  (2.0, 120.0),
    SoukCategory.VIANDE:  (25.0, 350.0),
    SoukCategory.POISSON: (8.0, 400.0),
}

# Fenêtre d'analyse pour la médiane de référence
_WINDOW_DAYS = 21
# Tolérance d'écart vs médiane avant de basculer en "à vérifier"
_LOW_FACTOR = 0.4
_HIGH_FACTOR = 2.5


@dataclass
class ModerationResult:
    status: SoukStatus
    reason: str | None
    source: str            # auto | claude


async def _reference_median(
    db: AsyncSession, item_name: str, city: str, unit: str,
) -> tuple[float | None, int]:
    """Médiane des relevés approuvés récents pour ce produit/ville/unité."""
    since = datetime.now(timezone.utc) - timedelta(days=_WINDOW_DAYS)
    stmt = (
        select(SoukPrice.price)
        .where(
            SoukPrice.status == SoukStatus.APPROVED,
            SoukPrice.is_active.is_(True),
            SoukPrice.unit == unit,
            SoukPrice.city.ilike(city),
            SoukPrice.item_name.ilike(item_name),
            SoukPrice.created_at >= since,
        )
    )
    rows = (await db.execute(stmt)).scalars().all()
    prices = [float(p) for p in rows]
    if not prices:
        return None, 0
    return statistics.median(prices), len(prices)


async def _claude_judgment(
    item_name: str, category: SoukCategory, unit: str, price: float,
    city: str, median: float | None,
) -> ModerationResult | None:
    """Demande à Claude de juger la plausibilité. Renvoie None si indisponible."""
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
        ctx = f"médiane récente du quartier : {median:.2f} MAD" if median else "aucun historique"
        prompt = (
            "Tu es modérateur de prix pour une app marocaine de courses. "
            "Juge si ce prix de souk est PLAUSIBLE au Maroc en 2026.\n"
            f"Produit : {item_name} ({category.value})\n"
            f"Prix : {price:.2f} MAD / {unit} — ville : {city} — {ctx}\n"
            'Réponds STRICTEMENT en JSON : {"verdict":"approved|pending|rejected","reason":"<courte raison FR>"}. '
            "approved = plausible ; pending = douteux à faire vérifier ; rejected = manifestement faux/frauduleux."
        )
        msg = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=150,
            messages=[{"role": "user", "content": prompt}],
        )
        import json
        raw = msg.content[0].text.strip()
        start, end = raw.find("{"), raw.rfind("}")
        data = json.loads(raw[start:end + 1])
        verdict = str(data.get("verdict", "")).lower()
        reason = str(data.get("reason", ""))[:300] or None
        mapping = {
            "approved": SoukStatus.APPROVED,
            "pending": SoukStatus.PENDING,
            "rejected": SoukStatus.REJECTED,
        }
        if verdict in mapping:
            return ModerationResult(mapping[verdict], reason, "claude")
    except Exception as exc:  # noqa: BLE001 — jamais bloquant
        logger.warning("[Souk] Modération Claude indisponible : %s", exc)
    return None


async def moderate(
    db: AsyncSession,
    *,
    item_name: str,
    category: SoukCategory,
    unit: str,
    price: float,
    city: str,
) -> ModerationResult:
    # 1. Garde-fous absolus
    if price <= 0 or price > 100_000:
        return ModerationResult(SoukStatus.REJECTED, "Prix hors limites.", "auto")

    # 2. Fourchette de bon sens (uniquement au kg)
    sane = True
    if unit.lower() == "kg" and category in _SANITY_KG:
        lo, hi = _SANITY_KG[category]
        sane = lo <= price <= hi

    # 3. Comparaison à la médiane récente
    median, sample = await _reference_median(db, item_name, city, unit)

    if median is not None:
        if _LOW_FACTOR * median <= price <= _HIGH_FACTOR * median:
            base = ModerationResult(SoukStatus.APPROVED, None, "auto")
        else:
            base = ModerationResult(
                SoukStatus.PENDING,
                f"Écart important vs médiane du quartier ({median:.2f} MAD).",
                "auto",
            )
    else:
        # Premier relevé pour ce produit/ville
        if sane:
            base = ModerationResult(SoukStatus.APPROVED, "Premier relevé, dans la fourchette.", "auto")
        else:
            base = ModerationResult(
                SoukStatus.PENDING,
                "Premier relevé hors fourchette habituelle — à vérifier par la communauté.",
                "auto",
            )

    # Si l'analyse absolue dit "aberrant au kg" mais pas encore rejeté, on rétrograde en pending
    if not sane and base.status == SoukStatus.APPROVED:
        base = ModerationResult(
            SoukStatus.PENDING,
            "Prix inhabituel pour cette catégorie — à confirmer.",
            "auto",
        )

    # 4. Renfort Claude uniquement sur les cas non tranchés (pending)
    if base.status == SoukStatus.PENDING:
        verdict = await _claude_judgment(item_name, category, unit, price, city, median)
        if verdict is not None:
            return verdict

    return base
