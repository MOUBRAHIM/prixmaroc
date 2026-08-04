"""
Router /api/dashboard

GET /api/dashboard   Dashboard complet pour l'utilisateur courant

Toutes les données sont agrégées en un minimum de requêtes SQL et mises en cache
Redis (TTL 5 min). La structure de réponse est conçue pour être consommée
directement par un frontend mobile/web sans traitement supplémentaire.

Architecture des requêtes :
  Q1 — Compteurs de base (scans, alertes, produits suivis)       — 1 requête
  Q2 — Économies ce mois  (agrégation sur OcrScan.parsed_data)   — 1 requête
  Q3 — Graphique 30j     (savings par jour)                      — Python (parsing JSON)
  Q4 — Économies cumul année                                     — dérivé de Q3 étendu
  Q5 — Magasin préféré   (COUNT par store_id sur OcrScan)        — 1 requête
  Q6 — Alertes actives avec prix courant                         — 1 requête jointure
  Q7 — Score économe     (heuristique multicritère)              — dérivé Q1+Q2+Q5
  Q8 — Magasin conseillé (promos × habitudes × distance)         — 2 requêtes
  Q9 — Prochaine liste   (top 5 items depuis habits)             — cache IA séparé
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import and_, case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import OcrScan, Price, PriceAlert, Product, Store, User
from app.models.ocr_scan import ScanStatus
from app.services.ia_service import HabitAnalyzer, ia_service
from app.utils.cache import TTL_SHORT, cache
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])

_TTL_DASHBOARD = TTL_SHORT   # 5 minutes


# ──────────────────────────────────────────────────────────────────────────────
# Schemas de réponse
# ──────────────────────────────────────────────────────────────────────────────

class DayPoint(BaseModel):
    date: str           # "YYYY-MM-DD"
    savings: float      # MAD économisés ce jour


class EconomiesData(BaseModel):
    ce_mois: float                  # Économies cumulées ce mois (MAD)
    cumul_annee: float              # Économies cumulées cette année (MAD)
    graphique_30j: list[DayPoint]   # Courbe des économies journalières


class StatistiquesData(BaseModel):
    tickets_scannes: int            # Total scans DONE
    produits_suivis: int            # Alertes prix actives
    magasin_prefere: str | None     # Enseigne la plus visitée
    score_econome: int              # 0-100 : indice d'efficacité d'achat


class AlerteActive(BaseModel):
    alert_id: int
    product_id: int
    product_name: str
    product_image: str | None
    target_price: float
    current_price: float | None     # Meilleur prix actuel en DB
    current_store: str | None
    is_triggered: bool              # current_price ≤ target_price


class MiniListItem(BaseModel):
    product_name: str
    product_id: int | None
    quantity: float
    estimated_price_total: float
    store_name: str | None
    is_promo: bool


class ProchaineListe(BaseModel):
    list_type: str
    total_estimated: float
    item_count: int
    top_items: list[MiniListItem]   # Top 5 pour l'aperçu
    fallback_mode: bool


class MagasinConseille(BaseModel):
    store_id: int
    nom: str
    ville: str | None
    distance: str | None           # "X.X km" si coordonnées disponibles
    economie_estimee: float        # Économies potentielles sur vos habitudes (MAD)
    nb_promos_pertinentes: int


class DashboardResponse(BaseModel):
    user_id: int
    generated_at: datetime
    economies: EconomiesData
    statistiques: StatistiquesData
    alertes_actives: list[AlerteActive]
    prochaine_liste: ProchaineListe | None
    magasin_conseille: MagasinConseille | None


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _effective_price(price_val: float, promo_val: float | None, is_promo: bool) -> float:
    if is_promo and promo_val:
        return promo_val
    return price_val


def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _parse_ocr_savings(scans: list[OcrScan], since: datetime) -> tuple[
    dict[str, float],   # date_str → savings
    float,              # total_since
]:
    """
    Extrait les économies depuis parsed_data de chaque scan.
    Calcul : pour les items avec is_promo=True → savings = unit_price - promo_price
    Pour les items sans promo_price → savings = 0 (on ne peut pas inférer)
    """
    daily: dict[str, float] = defaultdict(float)
    total = 0.0

    for scan in scans:
        if not scan.parsed_data:
            continue
        scan_date = scan.created_at
        if isinstance(scan_date, datetime):
            date_str = scan_date.strftime("%Y-%m-%d")
        else:
            date_str = str(scan_date)

        items = scan.parsed_data.get("items") or scan.parsed_data.get("products") or []
        for item in items:
            is_promo = bool(item.get("is_promo") or False)
            unit_price = float(item.get("unit_price") or item.get("price") or 0)
            promo_price = float(item.get("promo_price") or 0)
            qty = float(item.get("quantity") or item.get("qty") or 1)

            if is_promo and promo_price > 0 and unit_price > promo_price:
                saving = (unit_price - promo_price) * qty
                daily[date_str] += round(saving, 2)
                total += saving

    return dict(daily), round(total, 2)


# ──────────────────────────────────────────────────────────────────────────────
# Sous-routines de collecte (chacune = 1-2 requêtes SQL)
# ──────────────────────────────────────────────────────────────────────────────

async def _collect_base_stats(user_id: int, db: AsyncSession) -> dict[str, Any]:
    """Q1 : compteurs tickets, alertes, produits suivis + Q5 : magasin préféré."""
    # Scans DONE total
    scan_count_res = await db.execute(
        select(func.count())
        .where(OcrScan.user_id == user_id, OcrScan.status == ScanStatus.DONE)
    )
    ticket_count = scan_count_res.scalar_one()

    # Alertes actives
    alert_count_res = await db.execute(
        select(func.count())
        .where(PriceAlert.user_id == user_id, PriceAlert.is_active == True)
    )
    alert_count = alert_count_res.scalar_one()

    # Magasin préféré (store avec le plus de scans)
    pref_store_res = await db.execute(
        select(OcrScan.store_id, func.count().label("cnt"))
        .where(
            OcrScan.user_id == user_id,
            OcrScan.status == ScanStatus.DONE,
            OcrScan.store_id != None,
        )
        .group_by(OcrScan.store_id)
        .order_by(func.count().desc())
        .limit(1)
    )
    pref_store_row = pref_store_res.first()
    pref_store_name = None
    if pref_store_row:
        store = await db.get(Store, pref_store_row.store_id)
        pref_store_name = store.name if store else None

    return {
        "ticket_count": ticket_count,
        "alert_count": alert_count,
        "pref_store_name": pref_store_name,
    }


async def _collect_economies(
    user_id: int,
    db: AsyncSession,
    now: datetime,
) -> tuple[EconomiesData, list[OcrScan]]:
    """Q2+Q3+Q4 : économies depuis les scans OCR (30j + this year)."""
    year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day_30_ago = now - timedelta(days=30)

    # Un seul select pour les 30 derniers jours (couvre le graphique et le mois)
    scans_30d_res = await db.execute(
        select(OcrScan).where(
            OcrScan.user_id == user_id,
            OcrScan.status == ScanStatus.DONE,
            OcrScan.created_at >= day_30_ago,
            OcrScan.parsed_data != None,
        ).order_by(OcrScan.created_at)
    )
    scans_30d: list[OcrScan] = scans_30d_res.scalars().all()

    # Économies annuelles (scans depuis début d'année, hors 30j déjà chargés)
    scans_ytd_res = await db.execute(
        select(OcrScan).where(
            OcrScan.user_id == user_id,
            OcrScan.status == ScanStatus.DONE,
            OcrScan.created_at >= year_start,
            OcrScan.created_at < day_30_ago,
            OcrScan.parsed_data != None,
        )
    )
    scans_ytd: list[OcrScan] = scans_ytd_res.scalars().all()

    daily_30d, total_30d = _parse_ocr_savings(scans_30d, day_30_ago)
    _, total_ytd_extra = _parse_ocr_savings(scans_ytd, year_start)

    # Graphique 30j : rempli avec 0 pour les jours sans scan
    graphique: list[DayPoint] = []
    for i in range(30, -1, -1):
        d = (now - timedelta(days=i)).strftime("%Y-%m-%d")
        graphique.append(DayPoint(date=d, savings=round(daily_30d.get(d, 0.0), 2)))

    # Économies ce mois = scans depuis début du mois
    _, ce_mois = _parse_ocr_savings(
        [s for s in scans_30d if s.created_at >= month_start], month_start
    )

    cumul_annee = round(total_ytd_extra + total_30d, 2)

    return EconomiesData(
        ce_mois=ce_mois,
        cumul_annee=cumul_annee,
        graphique_30j=graphique,
    ), scans_30d


async def _collect_alertes(user_id: int, db: AsyncSession) -> list[AlerteActive]:
    """Q6 : alertes actives avec meilleur prix courant."""
    alerts_res = await db.execute(
        select(PriceAlert, Product)
        .join(Product, PriceAlert.product_id == Product.id)
        .where(PriceAlert.user_id == user_id, PriceAlert.is_active == True)
        .limit(10)
    )
    alert_rows = alerts_res.all()

    if not alert_rows:
        return []

    product_ids = [alert.product_id for alert, _ in alert_rows]

    # Meilleur prix actuel par produit (une seule requête)
    subq = (
        select(Price.product_id, func.max(Price.recorded_at).label("latest"))
        .where(Price.product_id.in_(product_ids))
        .group_by(Price.product_id, Price.store_id)
        .subquery()
    )
    prices_res = await db.execute(
        select(Price, Store)
        .join(Store, Price.store_id == Store.id)
        .join(subq, and_(
            Price.product_id == subq.c.product_id,
            Price.recorded_at == subq.c.latest,
        ))
        .where(Store.is_active == True)
    )
    # Garder meilleur prix par produit
    best_prices: dict[int, tuple[float, str]] = {}
    for price, store in prices_res.all():
        eff = _effective_price(float(price.price), float(price.promo_price) if price.promo_price else None, price.is_promo)
        pid = price.product_id
        if pid not in best_prices or eff < best_prices[pid][0]:
            best_prices[pid] = (eff, store.name)

    result: list[AlerteActive] = []
    for alert, product in alert_rows:
        cur = best_prices.get(alert.product_id)
        result.append(AlerteActive(
            alert_id=alert.id,
            product_id=product.id,
            product_name=product.name,
            product_image=product.image_url,
            target_price=float(alert.target_price),
            current_price=cur[0] if cur else None,
            current_store=cur[1] if cur else None,
            is_triggered=bool(cur and cur[0] <= float(alert.target_price)),
        ))
    return result


async def _collect_magasin_conseille(
    user_id: int,
    db: AsyncSession,
    user: User,
) -> MagasinConseille | None:
    """Q8 : magasin conseillé basé sur promos × habitudes utilisateur."""
    analyzer = HabitAnalyzer(window_days=90)
    habits = await analyzer.analyze(user_id, db)

    if not habits.habits:
        return None

    habit_product_ids = {h.product_id for h in habits.habits if h.product_id}
    freq_by_id = {h.product_id: h.purchase_frequency for h in habits.habits if h.product_id}

    if not habit_product_ids:
        return None

    # Promos actives sur les produits de l'habitude
    subq = (
        select(Price.product_id, Price.store_id, func.max(Price.recorded_at).label("latest"))
        .where(Price.is_promo == True, Price.product_id.in_(habit_product_ids))
        .group_by(Price.product_id, Price.store_id)
        .subquery()
    )
    promo_res = await db.execute(
        select(Price, Store)
        .join(Store, Price.store_id == Store.id)
        .join(subq, and_(
            Price.product_id == subq.c.product_id,
            Price.store_id == subq.c.store_id,
            Price.recorded_at == subq.c.latest,
        ))
        .where(
            Price.is_promo == True,
            Price.promo_price != None,
            Store.is_active == True,
        )
    )

    # Agrège par magasin : économie pondérée par fréquence
    store_savings: dict[int, float] = defaultdict(float)
    store_promo_count: dict[int, int] = defaultdict(int)
    store_obj: dict[int, Store] = {}

    for price, store in promo_res.all():
        regular = float(price.price)
        promo = float(price.promo_price)
        if regular <= promo:
            continue
        freq = freq_by_id.get(price.product_id, 0.1)
        savings_weighted = (regular - promo) * freq
        store_savings[store.id] += savings_weighted
        store_promo_count[store.id] += 1
        store_obj[store.id] = store

    if not store_savings:
        return None

    best_store_id = max(store_savings, key=lambda sid: store_savings[sid])
    best_store = store_obj[best_store_id]

    # Distance si user et store ont des coordonnées
    distance_str = None
    if (user.city and best_store.latitude and best_store.longitude):
        # On ne peut calculer la distance exacte sans les coords user
        # On indique juste la ville
        if user.city.lower() == (best_store.city or "").lower():
            distance_str = "même ville"
    if best_store.city:
        distance_str = distance_str or best_store.city

    return MagasinConseille(
        store_id=best_store.id,
        nom=best_store.name,
        ville=best_store.city,
        distance=distance_str,
        economie_estimee=round(store_savings[best_store_id], 2),
        nb_promos_pertinentes=store_promo_count[best_store_id],
    )


async def _collect_prochaine_liste(
    user_id: int,
    db: AsyncSession,
    user: User,
) -> ProchaineListe | None:
    """Q9 : miniature de la prochaine liste (top 5, sans Claude pour le dashboard)."""
    try:
        # Utilise le générateur en mode fallback (pas d'appel Claude) pour rester rapide
        from app.services.ia_service import HabitAnalyzer, ListGenerator
        analyzer = HabitAnalyzer(window_days=90)
        habits = await analyzer.analyze(user_id, db)

        if not habits.habits:
            return None

        generator = ListGenerator()
        current_prices = await generator._fetch_current_prices(habits, db)
        gl = generator._generate_fallback(user_id, "hebdo", None, habits, current_prices)

        return ProchaineListe(
            list_type=gl.list_type,
            total_estimated=gl.total_estimated,
            item_count=len(gl.items),
            top_items=[
                MiniListItem(
                    product_name=i.product_name,
                    product_id=i.product_id,
                    quantity=i.quantity,
                    estimated_price_total=i.estimated_price_total,
                    store_name=i.store_name,
                    is_promo=i.is_promo,
                )
                for i in gl.items[:5]
            ],
            fallback_mode=True,
        )
    except Exception:
        return None


def _compute_score_econome(
    ticket_count: int,
    economies_mois: float,
    avg_weekly_budget: float,
    alert_count: int,
) -> int:
    """
    Score d'efficacité d'achat (0–100).
    Composantes :
      - Fréquence de scan  (30 pts max) : 1 scan/semaine = parfait
      - Taux d'économie    (40 pts max) : economies_mois / budget_mensuel_estimé
      - Utilisation alertes (30 pts max) : ≥ 5 alertes = parfait
    """
    # Fréquence scan : normalise sur 4 scans/mois
    scan_score = min(30, int((ticket_count / max(1, 4)) * 30))

    # Taux économie
    budget_mensuel = avg_weekly_budget * 4.33 if avg_weekly_budget > 0 else 500.0
    saving_ratio = min(1.0, economies_mois / max(1.0, budget_mensuel * 0.15))
    saving_score = int(saving_ratio * 40)

    # Alertes
    alert_score = min(30, int((alert_count / 5) * 30))

    return min(100, scan_score + saving_score + alert_score)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/dashboard
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=DashboardResponse,
    summary="Dashboard personnel complet",
    description=(
        "Retourne en un seul appel toutes les données du tableau de bord : "
        "économies, statistiques, alertes, aperçu liste et magasin conseillé. "
        "Résultat mis en cache Redis 5 minutes."
    ),
)
async def get_dashboard(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = f"prixmaroc:dashboard:{current_user.id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    now = datetime.now(timezone.utc)

    # Lancement des collectes (séquentiel car certaines dépendent du précédent)
    base_stats = await _collect_base_stats(current_user.id, db)
    economies, scans_30d = await _collect_economies(current_user.id, db, now)
    alertes = await _collect_alertes(current_user.id, db)
    magasin = await _collect_magasin_conseille(current_user.id, db, current_user)
    prochaine = await _collect_prochaine_liste(current_user.id, db, current_user)

    # Score économe
    avg_weekly = prochaine.total_estimated / 1.0 if prochaine else 0.0
    score = _compute_score_econome(
        ticket_count=base_stats["ticket_count"],
        economies_mois=economies.ce_mois,
        avg_weekly_budget=avg_weekly,
        alert_count=base_stats["alert_count"],
    )

    response = DashboardResponse(
        user_id=current_user.id,
        generated_at=now,
        economies=economies,
        statistiques=StatistiquesData(
            tickets_scannes=base_stats["ticket_count"],
            produits_suivis=base_stats["alert_count"],
            magasin_prefere=base_stats["pref_store_name"],
            score_econome=score,
        ),
        alertes_actives=alertes,
        prochaine_liste=prochaine,
        magasin_conseille=magasin,
    )

    await cache.set(cache_key, response.model_dump(mode="json"), ttl=_TTL_DASHBOARD)
    return response
