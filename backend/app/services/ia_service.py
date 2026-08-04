"""
Service IA de recommandations — PrixMaroc
==========================================

Modules :
  HabitAnalyzer  — Analyse l'historique OCR pour extraire les habitudes d'achat
  ListGenerator  — Génère une liste de courses personnalisée via Claude Sonnet
  PromoAlerter   — Score et filtre les promotions pertinentes par utilisateur
  IAService      — Façade principale exposée aux routers

Architecture du flux :
  1. HabitAnalyzer lit OcrScan.parsed_data (JSON OCR) → UserHabits
  2. ListGenerator enrichit avec les prix DB, appelle Claude → GeneratedList
  3. PromoAlerter croise Price.is_promo avec les habitudes → list[PromoAlert]
"""
from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from difflib import SequenceMatcher
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Category, OcrScan, Price, Product, Store, User
from app.models.ocr_scan import ScanStatus

logger = logging.getLogger("prixmaroc.ia")


# ──────────────────────────────────────────────────────────────────────────────
# Structures de données internes
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class PurchaseHabit:
    """Habitude d'achat pour un produit spécifique."""
    product_name: str                    # Nom normalisé extrait des tickets
    product_id: int | None               # ID produit DB si match trouvé
    purchase_frequency: float            # 0.0–1.0 (fraction des semaines)
    avg_quantity: float                  # Quantité moyenne achetée
    avg_price: float                     # Prix moyen constaté (MAD)
    category: str | None                 # Catégorie DB ou heuristique
    is_recurrent: bool                   # True si frequency > 0.8
    last_seen: date                      # Date du dernier achat détecté
    total_purchases: int                 # Nombre total d'achats sur la période


@dataclass
class CategoryBudget:
    """Budget moyen par catégorie."""
    category: str
    avg_weekly_budget: float
    avg_monthly_budget: float
    promo_sensitivity: float             # 0.0–1.0 : fraction des achats en promo


@dataclass
class UserHabits:
    """Résultat complet de l'analyse des habitudes d'un utilisateur."""
    user_id: int
    analysis_window_days: int
    scan_count: int                      # Nombre de tickets analysés
    habits: list[PurchaseHabit]
    category_budgets: list[CategoryBudget]
    total_avg_weekly_budget: float
    recurrent_products: list[PurchaseHabit]  # Sous-ensemble : frequency > 0.8
    analyzed_at: datetime


@dataclass
class GeneratedListItem:
    """Un article de la liste générée par Claude."""
    product_name: str
    product_id: int | None
    quantity: float
    unit: str | None
    estimated_price_unit: float
    estimated_price_total: float
    store_id: int | None
    store_name: str | None
    is_promo: bool
    reasoning: str
    category: str = "Autres"              # Catégorie d'affichage (regroupement)


@dataclass
class GeneratedList:
    """Liste de courses complète générée par l'IA."""
    user_id: int
    list_type: str                       # hebdo | bi-mensuel | mensuel
    budget_max: float | None
    total_estimated: float
    items: list[GeneratedListItem]
    recommended_stores: list[str]
    budget_status: str                   # dans_budget | dépasse_budget | pas_de_budget
    global_reasoning: str
    generated_at: datetime
    claude_model: str
    fallback_mode: bool                  # True si Claude indisponible → règles déterministes


@dataclass
class PromoAlert:
    """Alerte promo personnalisée pour un utilisateur."""
    product_id: int
    product_name: str
    product_image: str | None
    store_id: int
    store_name: str
    store_city: str | None
    regular_price: float
    promo_price: float
    discount_pct: float
    purchase_frequency: float            # De l'historique utilisateur
    relevance_score: float               # frequency × discount_ratio
    reason: str                          # Explication lisible
    recorded_at: datetime


# ──────────────────────────────────────────────────────────────────────────────
# Prompt Système Claude (complet)
# ──────────────────────────────────────────────────────────────────────────────

CLAUDE_SYSTEM_PROMPT = """Tu es l'assistant IA de PrixMaroc, une application de comparaison de prix pour les consommateurs marocains.

Ton rôle est de générer des listes de courses personnalisées et intelligentes basées sur :
- L'historique d'achats réel de l'utilisateur (tickets de caisse scannés via OCR)
- Les prix actuels relevés dans les grandes surfaces marocaines
- Les promotions en cours
- Le budget indiqué par l'utilisateur

═══════════════════════════════════════
CONTEXTE MARCHÉ MAROCAIN
═══════════════════════════════════════
- La devise est le Dirham marocain (MAD / DH)
- Les enseignes couvertes : Marjane, Carrefour Maroc, Label'Vie, BIM, Kazyon, Sopreco
- Les prix des produits de première nécessité (farine, sucre, huile de table, lait pasteurisé) sont partiellement subventionnés ou plafonnés
- Les cycles promo sont fréquents : début de mois (1–5), fin de mois (25–31), périodes de fête (Ramadan, Aid)
- Certains foyers achètent en gros mensuel : huile (5L × 2), sucre (5kg), farine (10kg)
- Les produits frais (viande, légumes) varient selon le souk/marché local et ne sont pas représentés

═══════════════════════════════════════
DONNÉES QUE TU REÇOIS
═══════════════════════════════════════
Tu reçois un objet JSON avec les champs suivants :

• user_context        : Profil (ville, budget habituel)
• list_type           : "hebdo" (7 jours) | "bi-mensuel" (15 jours) | "mensuel" (30 jours)
• budget_max          : Budget maximum en MAD (null = pas de limite)
• habits              : Liste d'habitudes d'achat extraites des tickets
  - product_name      : Nom du produit
  - product_id        : ID en base (null si inconnu)
  - purchase_frequency: Float 0-1 (ex: 0.9 = acheté 9 semaines sur 10)
  - avg_quantity       : Quantité moyenne par achat
  - avg_price         : Prix moyen constaté en MAD
  - is_recurrent      : True si frequency > 0.8
  - category          : Catégorie (null si inconnue)
• current_prices      : Prix actuels DB par produit
  - product_id, product_name, cheapest_price, cheapest_store, is_promo, promo_price
• active_promos       : Promotions en cours (triées par remise décroissante)

═══════════════════════════════════════
INSTRUCTIONS DE GÉNÉRATION
═══════════════════════════════════════
1. PRIORITÉS D'INCLUSION :
   - Obligatoire  : Produits avec purchase_frequency > 0.8 (récurrents)
   - Prioritaire  : Produits avec purchase_frequency > 0.5 ET en promo actuellement
   - Optionnel    : Produits avec purchase_frequency > 0.3 si budget disponible

2. QUANTITÉS :
   - Base : avg_quantity × (list_type_days / 7)
   - Arrondi à l'unité supérieure pour les emballages entiers
   - Pour "mensuel" : suggère conditionnement gros format si disponible

3. GESTION DU BUDGET :
   - Si budget_max défini, respecte-le STRICTEMENT (total_estimated ≤ budget_max)
   - En cas de dépassement : retire en priorité les produits optionnels, puis réduis les quantités
   - Indique budget_status : "dans_budget" | "dépasse_budget" | "pas_de_budget"

4. OPTIMISATION MAGASIN :
   - Préfère les magasins avec le plus de produits pour minimiser les déplacements
   - Indique le magasin conseillé par article (celui avec le meilleur prix)
   - recommended_stores : max 3 enseignes, triées par nombre de produits à acheter

5. PROMOTIONS :
   - Signale is_promo = true pour tout article actuellement en promotion
   - Dans reasoning, mentionne le % de réduction si pertinent

6. RAISONNEMENT :
   - reasoning par item : 1–2 phrases max, en français, lisible par un consommateur
   - global_reasoning : synthèse de la stratégie d'achat choisie (3–5 phrases)

═══════════════════════════════════════
FORMAT DE RÉPONSE (JSON strict)
═══════════════════════════════════════
Réponds UNIQUEMENT avec le JSON suivant, sans aucun texte avant ou après :

{
  "items": [
    {
      "product_name": "Lait Centrale entier 1L",
      "product_id": 42,
      "quantity": 6,
      "unit": "unité",
      "estimated_price_unit": 8.50,
      "estimated_price_total": 51.00,
      "store_id": 3,
      "store_name": "Marjane Hay Riad",
      "is_promo": true,
      "reasoning": "Acheté chaque semaine en moyenne 2 unités. Actuellement en promo -15% chez Marjane."
    }
  ],
  "total_estimated": 234.50,
  "recommended_stores": ["Marjane Hay Riad", "BIM Agdal"],
  "budget_status": "dans_budget",
  "global_reasoning": "Liste de 7 jours optimisée sur 2 magasins. 4 produits en promo cette semaine représentant 18 DH d'économies."
}

═══════════════════════════════════════
RÈGLES ABSOLUES
═══════════════════════════════════════
- Ne JAMAIS inventer un produit absent des données fournies
- Ne JAMAIS dépasser budget_max si spécifié
- product_id doit être l'ID exact des données d'entrée (null si non fourni)
- Les prix doivent provenir de current_prices ou active_promos (jamais inventés)
- Répondre UNIQUEMENT avec le JSON, zéro texte hors structure
- Tous les montants en MAD avec 2 décimales
"""


# ──────────────────────────────────────────────────────────────────────────────
# Utilitaires
# ──────────────────────────────────────────────────────────────────────────────

def _normalize_name(name: str) -> str:
    """Normalise un nom produit pour la comparaison fuzzy."""
    name = name.lower().strip()
    name = re.sub(r"[^\w\s]", " ", name)
    name = re.sub(r"\s+", " ", name)
    return name


def _fuzzy_score(a: str, b: str) -> float:
    return SequenceMatcher(None, _normalize_name(a), _normalize_name(b)).ratio()


def _isoweek(dt: datetime | date) -> tuple[int, int]:
    """Retourne (year, week) ISO d'une date."""
    d = dt.date() if isinstance(dt, datetime) else dt
    return d.isocalendar()[:2]


def _days_for_type(list_type: str) -> int:
    return {"hebdo": 7, "bi-mensuel": 15, "mensuel": 30}.get(list_type, 7)


# ──────────────────────────────────────────────────────────────────────────────
# HabitAnalyzer
# ──────────────────────────────────────────────────────────────────────────────

class HabitAnalyzer:
    """
    Analyse l'historique des tickets OCR pour extraire les habitudes d'achat.

    Algorithme :
      1. Charge tous les OcrScan (status=DONE) sur `window_days` jours
      2. Extrait les items de chaque parsed_data
      3. Regroupe par nom normalisé (fuzzy 0.80)
      4. Calcule frequency = semaines_achetées / total_semaines_window
      5. Tente un match DB Product via fuzzy (seuil 0.75)
      6. Agrège les budgets par catégorie
    """

    FUZZY_MERGE_THRESHOLD = 0.80      # Seuil pour fusionner deux noms comme identiques
    DB_MATCH_THRESHOLD    = 0.75      # Seuil pour lier à un produit DB
    RECURRENT_THRESHOLD   = 0.80      # Seuil fréquence → produit récurrent

    def __init__(self, window_days: int = 90):
        self.window_days = window_days

    async def analyze(self, user_id: int, db: AsyncSession) -> UserHabits:
        since = datetime.now(timezone.utc) - timedelta(days=self.window_days)

        # ── 1. Charger les scans ──────────────────────────────────────────────
        stmt = select(OcrScan).where(
            OcrScan.user_id == user_id,
            OcrScan.status == ScanStatus.DONE,
            OcrScan.created_at >= since,
            OcrScan.parsed_data != None,
        ).order_by(OcrScan.created_at)
        result = await db.execute(stmt)
        scans: list[OcrScan] = result.scalars().all()

        if not scans:
            return UserHabits(
                user_id=user_id,
                analysis_window_days=self.window_days,
                scan_count=0,
                habits=[],
                category_budgets=[],
                total_avg_weekly_budget=0.0,
                recurrent_products=[],
                analyzed_at=datetime.now(timezone.utc),
            )

        # ── 2. Extraire les items de chaque scan ──────────────────────────────
        # Structure attendue : {"items": [{"name": str, "quantity": float,
        #                                  "unit_price": float, "total_price": float}]}
        raw_items: list[dict] = []
        for scan in scans:
            pd = scan.parsed_data
            if not pd:
                continue
            items = pd.get("items") or pd.get("products") or []
            scan_date = scan.created_at
            for item in items:
                name = (item.get("name") or item.get("product_name") or "").strip()
                if not name:
                    continue
                raw_items.append({
                    "name": name,
                    "quantity": float(item.get("quantity") or item.get("qty") or 1),
                    "unit_price": float(item.get("unit_price") or item.get("price") or 0),
                    "total_price": float(item.get("total_price") or item.get("total") or 0),
                    "is_promo": bool(item.get("is_promo") or False),
                    "week": _isoweek(scan_date),
                    "date": scan_date.date() if isinstance(scan_date, datetime) else scan_date,
                })

        # ── 3. Fusionner les noms similaires (fuzzy clustering) ────────────────
        clusters: dict[str, list[dict]] = {}  # canonical_name → items

        for item in raw_items:
            best_match: str | None = None
            best_score = 0.0
            for canon in clusters:
                score = _fuzzy_score(item["name"], canon)
                if score > best_score:
                    best_score = score
                    best_match = canon
            if best_match and best_score >= self.FUZZY_MERGE_THRESHOLD:
                clusters[best_match].append(item)
            else:
                clusters[item["name"]] = [item]

        # ── 4. Calculer les métriques par produit ─────────────────────────────
        total_weeks = max(1, self.window_days // 7)

        # Charger tous les produits DB pour le matching (nom seulement)
        db_products_res = await db.execute(
            select(Product.id, Product.name, Product.category_id)
            .where(Product.is_active == True)
        )
        db_products = db_products_res.all()  # list of (id, name, category_id)

        # Cache catégories
        cat_cache: dict[int, str] = {}

        async def _get_cat_name(cat_id: int | None) -> str | None:
            if cat_id is None:
                return None
            if cat_id in cat_cache:
                return cat_cache[cat_id]
            cat = await db.get(Category, cat_id)
            cat_name = cat.name if cat else None
            if cat_name:
                cat_cache[cat_id] = cat_name
            return cat_name

        habits: list[PurchaseHabit] = []

        for canon_name, items in clusters.items():
            weeks_present = len({i["week"] for i in items})
            frequency = round(weeks_present / total_weeks, 3)
            quantities = [i["quantity"] for i in items if i["quantity"] > 0]
            prices = [i["unit_price"] for i in items if i["unit_price"] > 0]
            promo_count = sum(1 for i in items if i["is_promo"])
            last_date = max(i["date"] for i in items)

            avg_qty = round(sum(quantities) / len(quantities), 2) if quantities else 1.0
            avg_price = round(sum(prices) / len(prices), 2) if prices else 0.0

            # Match DB product
            matched_id: int | None = None
            matched_cat: str | None = None
            best_db_score = 0.0
            for db_id, db_name, db_cat_id in db_products:
                score = _fuzzy_score(canon_name, db_name)
                if score > best_db_score:
                    best_db_score = score
                    if score >= self.DB_MATCH_THRESHOLD:
                        matched_id = db_id
                        matched_cat = await _get_cat_name(db_cat_id)

            habits.append(PurchaseHabit(
                product_name=canon_name,
                product_id=matched_id,
                purchase_frequency=frequency,
                avg_quantity=avg_qty,
                avg_price=avg_price,
                category=matched_cat or _heuristic_category(canon_name),
                is_recurrent=frequency >= self.RECURRENT_THRESHOLD,
                last_seen=last_date,
                total_purchases=len(items),
            ))

        habits.sort(key=lambda h: h.purchase_frequency, reverse=True)

        # ── 5. Budget par catégorie ───────────────────────────────────────────
        cat_spend: dict[str, list[float]] = defaultdict(list)
        cat_promo: dict[str, list[bool]] = defaultdict(list)

        for scan in scans:
            pd = scan.parsed_data
            if not pd:
                continue
            week_key = _isoweek(scan.created_at)
            week_spend_by_cat: dict[str, float] = defaultdict(float)
            for item in (pd.get("items") or pd.get("products") or []):
                name = (item.get("name") or "").strip()
                total = float(item.get("total_price") or item.get("total") or 0)
                is_promo = bool(item.get("is_promo") or False)
                cat = _heuristic_category(name)
                week_spend_by_cat[cat] += total
                cat_promo[cat].append(is_promo)
            for cat, spend in week_spend_by_cat.items():
                cat_spend[cat].append(spend)

        category_budgets: list[CategoryBudget] = []
        for cat, weekly_spends in cat_spend.items():
            avg_w = round(sum(weekly_spends) / total_weeks, 2)
            promo_flags = cat_promo.get(cat, [])
            promo_sens = round(sum(promo_flags) / len(promo_flags), 3) if promo_flags else 0.0
            category_budgets.append(CategoryBudget(
                category=cat,
                avg_weekly_budget=avg_w,
                avg_monthly_budget=round(avg_w * 4.33, 2),
                promo_sensitivity=promo_sens,
            ))
        category_budgets.sort(key=lambda c: c.avg_weekly_budget, reverse=True)

        total_avg_weekly = round(
            sum(sum(spends) / total_weeks for spends in cat_spend.values()), 2
        )

        return UserHabits(
            user_id=user_id,
            analysis_window_days=self.window_days,
            scan_count=len(scans),
            habits=habits,
            category_budgets=category_budgets,
            total_avg_weekly_budget=total_avg_weekly,
            recurrent_products=[h for h in habits if h.is_recurrent],
            analyzed_at=datetime.now(timezone.utc),
        )


def _heuristic_category(name: str) -> str:
    """Catégorisation heuristique par mots-clés quand la DB ne matche pas."""
    n = name.lower()
    if any(k in n for k in ["lait", "yaourt", "fromage", "beurre", "crème"]):
        return "Produits laitiers"
    if any(k in n for k in ["pain", "farine", "semoule", "brioche", "baguette"]):
        return "Boulangerie / Céréales"
    if any(k in n for k in ["huile", "olive", "tournesol"]):
        return "Huiles"
    if any(k in n for k in ["sucre", "miel", "confiture", "chocolat"]):
        return "Sucre / Confiserie"
    if any(k in n for k in ["eau", "jus", "boisson", "soda", "café", "thé"]):
        return "Boissons"
    if any(k in n for k in ["poulet", "viande", "bœuf", "agneau", "poisson", "kefta"]):
        return "Viandes / Poissons"
    if any(k in n for k in ["riz", "pâtes", "couscous", "lentille", "pois chiche"]):
        return "Épicerie sèche"
    if any(k in n for k in ["shampoing", "savon", "dentifrice", "gel", "déodorant"]):
        return "Hygiène"
    if any(k in n for k in ["lessive", "nettoyant", "javel", "liquide vaisselle"]):
        return "Entretien"
    if any(k in n for k in ["couche", "lingette", "serviette hygiénique"]):
        return "Bébé / Hygiène féminine"
    return "Divers"


# ──────────────────────────────────────────────────────────────────────────────
# ListGenerator
# ──────────────────────────────────────────────────────────────────────────────

class ListGenerator:
    """
    Génère une liste de courses personnalisée.

    Flux :
      1. Analyse les habitudes via HabitAnalyzer
      2. Récupère les prix actuels en DB pour les produits reconnus
      3. Construit le payload Claude
      4. Appelle claude-sonnet, parse le JSON
      5. Si Claude indisponible → fallback déterministe (top produits récurrents)
    """

    MODEL = "claude-sonnet-4-6"
    MAX_HABITS_IN_PROMPT = 30          # Limite pour le contexte Claude
    MAX_PROMOS_IN_PROMPT = 20

    def __init__(self):
        self._client = None

    def _get_client(self):
        """Lazy init du client Anthropic."""
        if self._client is not None:
            return self._client
        if not settings.ANTHROPIC_API_KEY:
            return None
        try:
            import anthropic
            self._client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            return self._client
        except ImportError:
            logger.warning("[IA] Package 'anthropic' non installé — mode fallback activé")
            return None

    async def generate(
        self,
        user_id: int,
        list_type: str,
        budget_max: float | None,
        db: AsyncSession,
        user: User | None = None,
        household_size: int = 1,
    ) -> GeneratedList:
        # ── Analyse des habitudes ─────────────────────────────────────────────
        analyzer = HabitAnalyzer(window_days=90)
        habits = await analyzer.analyze(user_id, db)

        # ── Prix actuels DB ───────────────────────────────────────────────────
        current_prices = await self._fetch_current_prices(habits, db)

        # ── Promotions actives ────────────────────────────────────────────────
        active_promos = await self._fetch_active_promos(db, limit=self.MAX_PROMOS_IN_PROMPT)

        # ── Appel Claude ──────────────────────────────────────────────────────
        client = self._get_client()
        if client:
            return await self._generate_via_claude(
                client, user_id, list_type, budget_max,
                habits, current_prices, active_promos, user,
                db=db, household_size=household_size,
            )
        else:
            logger.warning("[IA] Claude indisponible — génération déterministe")
            return await self._generate_fallback(
                user_id, list_type, budget_max, habits, current_prices,
                db=db, household_size=household_size,
            )

    async def _fetch_current_prices(
        self,
        habits: UserHabits,
        db: AsyncSession,
    ) -> list[dict]:
        """Récupère le prix le plus bas actuel pour chaque produit reconnu."""
        product_ids = [h.product_id for h in habits.habits if h.product_id]
        if not product_ids:
            return []

        subq = (
            select(
                Price.product_id,
                Price.store_id,
                func.max(Price.recorded_at).label("latest"),
            )
            .where(Price.product_id.in_(product_ids))
            .group_by(Price.product_id, Price.store_id)
            .subquery()
        )
        stmt = (
            select(Price, Product, Store)
            .join(Product, Price.product_id == Product.id)
            .join(Store, Price.store_id == Store.id)
            .join(subq, and_(
                Price.product_id == subq.c.product_id,
                Price.store_id == subq.c.store_id,
                Price.recorded_at == subq.c.latest,
            ))
            .where(Store.is_active == True, Product.is_active == True)
        )
        result = await db.execute(stmt)
        rows = result.all()

        # Garder le prix le moins cher par produit
        best: dict[int, dict] = {}
        for price, product, store in rows:
            eff = float(price.promo_price) if price.is_promo and price.promo_price else float(price.price)
            if price.product_id not in best or eff < best[price.product_id]["cheapest_price"]:
                best[price.product_id] = {
                    "product_id": product.id,
                    "product_name": product.name,
                    "cheapest_price": eff,
                    "regular_price": float(price.price),
                    "cheapest_store_id": store.id,
                    "cheapest_store": store.name,
                    "is_promo": price.is_promo,
                    "promo_price": float(price.promo_price) if price.promo_price else None,
                }
        return list(best.values())

    async def _fetch_active_promos(self, db: AsyncSession, limit: int = 20) -> list[dict]:
        """Récupère les promotions actuellement actives triées par remise."""
        subq = (
            select(
                Price.product_id,
                Price.store_id,
                func.max(Price.recorded_at).label("latest"),
            )
            .where(Price.is_promo == True)
            .group_by(Price.product_id, Price.store_id)
            .subquery()
        )
        stmt = (
            select(Price, Product, Store)
            .join(Product, Price.product_id == Product.id)
            .join(Store, Price.store_id == Store.id)
            .join(subq, and_(
                Price.product_id == subq.c.product_id,
                Price.store_id == subq.c.store_id,
                Price.recorded_at == subq.c.latest,
            ))
            .where(
                Price.is_promo == True,
                Price.promo_price != None,
                Product.is_active == True,
                Store.is_active == True,
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        promos = []
        for price, product, store in result.all():
            regular = float(price.price)
            promo = float(price.promo_price)
            if regular > 0 and promo < regular:
                discount = round((regular - promo) / regular * 100, 1)
                promos.append({
                    "product_id": product.id,
                    "product_name": product.name,
                    "store_id": store.id,
                    "store_name": store.name,
                    "regular_price": regular,
                    "promo_price": promo,
                    "discount_pct": discount,
                })
        promos.sort(key=lambda p: p["discount_pct"], reverse=True)
        return promos

    async def _generate_via_claude(
        self,
        client,
        user_id: int,
        list_type: str,
        budget_max: float | None,
        habits: UserHabits,
        current_prices: list[dict],
        active_promos: list[dict],
        user: User | None,
        db: AsyncSession | None = None,
        household_size: int = 1,
    ) -> GeneratedList:
        """Construit le payload et appelle Claude Sonnet."""
        days = _days_for_type(list_type)

        habits_payload = [
            {
                "product_name": h.product_name,
                "product_id": h.product_id,
                "purchase_frequency": h.purchase_frequency,
                "avg_quantity": h.avg_quantity,
                "avg_price": h.avg_price,
                "is_recurrent": h.is_recurrent,
                "category": h.category,
            }
            for h in habits.habits[:self.MAX_HABITS_IN_PROMPT]
        ]

        user_context = {
            "city": user.city if user else None,
            "avg_weekly_budget_observed": habits.total_avg_weekly_budget,
            "scan_count": habits.scan_count,
            "top_categories": [
                {"category": cb.category, "avg_weekly_budget": cb.avg_weekly_budget}
                for cb in habits.category_budgets[:5]
            ],
        }

        user_message = json.dumps({
            "user_context": user_context,
            "list_type": list_type,
            "list_days": days,
            "budget_max": budget_max,
            "habits": habits_payload,
            "current_prices": current_prices,
            "active_promos": active_promos[:self.MAX_PROMOS_IN_PROMPT],
        }, ensure_ascii=False, default=str)

        logger.info(f"[IA] Appel Claude pour user={user_id}, type={list_type}, budget={budget_max}")

        try:
            message = await client.messages.create(
                model=self.MODEL,
                max_tokens=4096,
                system=CLAUDE_SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_message}],
            )
            raw_response = message.content[0].text
            logger.debug(f"[IA] Réponse Claude brute ({len(raw_response)} chars)")

            parsed = self._parse_claude_response(raw_response)
            return self._build_generated_list(
                user_id, list_type, budget_max, parsed,
                model=self.MODEL, fallback=False,
            )

        except Exception as exc:
            logger.error(f"[IA] Erreur Claude API : {exc}", exc_info=True)
            return await self._generate_fallback(
                user_id, list_type, budget_max, habits, current_prices,
                db=db, household_size=household_size,
            )

    def _parse_claude_response(self, raw: str) -> dict:
        """Parse la réponse JSON de Claude avec tolérance aux erreurs."""
        # Tentative directe
        raw = raw.strip()
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # Extrait le bloc JSON si enrobé dans du texte ou markdown
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(1))
            except json.JSONDecodeError:
                pass

        # Dernier recours : extrait le premier {...} de la réponse
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass

        logger.warning("[IA] Impossible de parser la réponse Claude — structure vide")
        return {"items": [], "total_estimated": 0, "recommended_stores": [],
                "budget_status": "pas_de_budget", "global_reasoning": ""}

    def _build_generated_list(
        self,
        user_id: int,
        list_type: str,
        budget_max: float | None,
        parsed: dict,
        model: str,
        fallback: bool,
    ) -> GeneratedList:
        items: list[GeneratedListItem] = []
        for raw_item in parsed.get("items", []):
            items.append(GeneratedListItem(
                product_name=raw_item.get("product_name", ""),
                product_id=raw_item.get("product_id"),
                quantity=float(raw_item.get("quantity", 1)),
                unit=raw_item.get("unit"),
                estimated_price_unit=float(raw_item.get("estimated_price_unit", 0)),
                estimated_price_total=float(raw_item.get("estimated_price_total", 0)),
                store_id=raw_item.get("store_id"),
                store_name=raw_item.get("store_name"),
                is_promo=bool(raw_item.get("is_promo", False)),
                reasoning=raw_item.get("reasoning", ""),
            ))
        return GeneratedList(
            user_id=user_id,
            list_type=list_type,
            budget_max=budget_max,
            total_estimated=float(parsed.get("total_estimated", sum(i.estimated_price_total for i in items))),
            items=items,
            recommended_stores=parsed.get("recommended_stores", []),
            budget_status=parsed.get("budget_status", "pas_de_budget"),
            global_reasoning=parsed.get("global_reasoning", ""),
            generated_at=datetime.now(timezone.utc),
            claude_model=model,
            fallback_mode=fallback,
        )

    async def _generate_fallback(
        self,
        user_id: int,
        list_type: str,
        budget_max: float | None,
        habits: UserHabits,
        current_prices: list[dict],
        db: AsyncSession | None = None,
        household_size: int = 1,
    ) -> GeneratedList:
        """
        Génération déterministe basée sur un plan nutritionnel marocain complet.

        Couvre les 5 groupes nutritionnels essentiels :
          • Glucides complexes  (55 % de l'énergie) — farine, couscous, pâtes, riz
          • Protéines animales  (20 %)              — sardines, thon, lait, yaourt, fromage
          • Lipides essentiels  (25 %)              — huile végétale, beurre/margarine
          • Micronutriments                         — tomates, harissa, jus de fruits
          • Hydratation + culture marocaine         — eau, thé, café, sucre
        + Hygiène & entretien du foyer

        Quantités calibrées pour un foyer marocain réel et ajustées selon
        household_size (nombre de personnes) et la durée (hebdo/bi-mensuel/mensuel).
        """
        days = _days_for_type(list_type)
        weeks = days / 7.0
        price_map = {p["product_id"]: p for p in current_prices}
        items: list[GeneratedListItem] = []
        total = 0.0

        # ── 1. Depuis les habitudes (si existantes) ───────────────────────────
        if habits.habits:
            for habit in habits.habits:
                if habit.purchase_frequency < 0.3:
                    continue
                qty = max(1, round(habit.avg_quantity * weeks * household_size))
                price_info = price_map.get(habit.product_id) if habit.product_id else None
                unit_price = price_info["cheapest_price"] if price_info else habit.avg_price
                line_total = round(unit_price * qty, 2)
                if budget_max and (total + line_total) > budget_max:
                    break
                items.append(GeneratedListItem(
                    product_name=habit.product_name,
                    product_id=habit.product_id,
                    quantity=float(qty),
                    unit=None,
                    estimated_price_unit=unit_price,
                    estimated_price_total=line_total,
                    store_id=price_info["cheapest_store_id"] if price_info else None,
                    store_name=price_info["cheapest_store"] if price_info else None,
                    is_promo=price_info["is_promo"] if price_info else False,
                    reasoning=f"Acheté régulièrement — {household_size} personne(s), {days} jours.",
                ))
                total += line_total

        # ── 2. Plan nutritionnel marocain complet (si pas d'historique) ───────
        if not items and db is not None:
            from sqlalchemy import select, func as sqlfunc
            from app.models import Product, Price, Store

            # ── Niveau de pouvoir d'achat ─────────────────────────────────────
            # Calculé sur budget_max / foyer / semaine :
            #   NIVEAU 1 — Économique  : < 150 DH/pers/semaine  (foyer modeste)
            #   NIVEAU 2 — Standard    : 150–350 DH/pers/semaine (classe moyenne)
            #   NIVEAU 3 — Confortable : > 350 DH/pers/semaine  (panier complet)
            # Sans budget → niveau 3 (liste optimale complète)
            if budget_max:
                bpw = budget_max / household_size / weeks   # DH / personne / semaine
                tier = 1 if bpw < 150 else (2 if bpw < 350 else 3)
            else:
                tier = 3

            # ── Plan nutritionnel ─────────────────────────────────────────────
            # Colonnes: (rôle, mots-clés prioritaires, qté/pers/sem, justification, niveau_min)
            #
            # niveau_min = niveau minimum de pouvoir d'achat requis pour inclure cet article :
            #   1 = essentiel absolu (tout foyer, même très modeste)
            #   2 = nutrition équilibrée (classe moyenne)
            #   3 = panier optimal/confort (pouvoir d'achat élevé)
            #
            # Référence : OMS + ONSSA + Guide alimentaire marocain
            # Adulte actif ~2 000 kcal/j : 275 g glucides, 75 g protéines, 65 g lipides
            # Colonnes: (rôle, keywords, qté/pers/sem, justification, tier_min, catégorie)
            NUTRITION_PLAN: list[tuple[str, list[str], float, str, int, str]] = [
                # ══════════════════════════════════════════════════════════════
                # NIVEAU 1 — ESSENTIELS ABSOLUS
                # Couverture nutritionnelle minimale pour tout foyer marocain,
                # même avec un budget très serré (< 150 DH/pers/semaine)
                # ══════════════════════════════════════════════════════════════

                # ── Eau ───────────────────────────────────────────────────────
                (
                    "Eau minérale",
                    ["bahia 1.5", "sidi ali 1.5", "bahia", "sidi ali", "eau min"],
                    3.5,
                    "Hydratation — 1,5 à 2 L/jour recommandés par l'OMS, "
                    "essentiel au transport des nutriments et à la thermorégulation",
                    1,
                ),
                # ── Farine & Pain — alimentation de base ──────────────────────
                (
                    "Farine tendre (khobz quotidien)",
                    ["farine tendre", "farine ilycia", "farine"],
                    1.5,
                    "Glucides complexes — base du pain marocain (khobz) cuit 2×/jour, "
                    "apporte fibres, fer, vitamines B1/B9 ; staple n°1 du foyer marocain",
                    1,
                ),
                (
                    "Levure boulangère (khobz & msemen)",
                    ["levure de boulanger", "saf-instant", "levure"],
                    0.15,
                    "Fermentation — indispensable pour lever le pain marocain (khobz), "
                    "msemen et meloui ; enrichit en vit B (thiamine, riboflavine, niacine)",
                    1,
                ),
                # ── Œufs — protéine économique universelle ─────────────────────
                (
                    "Œufs frais",
                    ["oeufs frais catégorie a 12", "oeufs frais catégorie a 6",
                     "oeufs frais"],
                    1.0,
                    "Protéines complètes (13 g/100 g, score DIAAS = 1,0) + fer + zinc "
                    "+ vit A + vit D + choline (cerveau) + lécithine "
                    "— incontournables : œuf sur le plat, chakchouka, briouates, kefta ; "
                    "protéine animale la plus économique au Maroc (~1,8 DH/œuf)",
                    1,
                ),
                # ── Sel — condiment de base ────────────────────────────────────
                (
                    "Sel fin",
                    ["sel fin 1kg", "sel fin"],
                    0.1,
                    "Chlorure de sodium — indispensable à toute cuisine, "
                    "régulation de l'équilibre hydrique et du système nerveux",
                    1,
                ),
                # ── Huile végétale ─────────────────────────────────────────────
                (
                    "Huile végétale (cuisson)",
                    ["huile de tournesol lesieur", "huile de soja cristal",
                     "huile tournesol", "huile soja"],
                    0.25,
                    "Acides gras essentiels oméga-6 (linoléique) + vit E antioxydante "
                    "+ vit K — cuisson quotidienne de tous les plats marocains",
                    1,
                ),
                # ── Légumineuses — protéines végétales économiques ─────────────
                (
                    "Pois chiches (harira, couscous, lablabi)",
                    ["pois chiches secs 1kg", "pois chiches"],
                    0.4,
                    "Protéines végétales (19 g/100 g) + fibres (17 g) + fer (6,2 mg) "
                    "+ acide folique + zinc + magnésium — base de la harira (soupe nationale), "
                    "couscous du vendredi ; coût ≈ 14 DH/kg pour 5–6 portions",
                    1,
                ),
                (
                    "Lentilles vertes (harira, soupe)",
                    ["lentilles vertes 1kg", "lentilles"],
                    0.3,
                    "Protéines (26 g/100 g sec) + fer (8 mg) + folates (181 µg) "
                    "+ fibres solubles (antiglycémiant) — harira, soupe d'hiver, "
                    "index glycémique bas (29), protéine végétale la plus complète",
                    1,
                ),
                # ── Légumes de base ────────────────────────────────────────────
                (
                    "Tomates fraîches",
                    ["tomates fraîches 1kg", "tomates fraîches"],
                    1.5,
                    "Vit C (21 mg/100 g) + lycopène antioxydant + potassium + folates "
                    "— ingrédient fondateur de la cuisine marocaine : tagines, salades, harira, "
                    "taktouka (salade tomates-poivrons), chakchouka",
                    1,
                ),
                (
                    "Oignons",
                    ["oignons 1kg", "oignons"],
                    1.0,
                    "Quercétine antioxydante + vit C + prébiotiques (inuline) + soufre "
                    "— arôme de base de 95 % des plats marocains ; base de toutes les sauces tagines",
                    1,
                ),
                (
                    "Pommes de terre",
                    ["pommes de terre 1kg", "pommes de terre"],
                    1.5,
                    "Glucides complexes (17 g/100 g) + potassium (421 mg) + vit C + vit B6 "
                    "— légume le plus consommé au Maroc ; tagine poulet-pommes de terre, "
                    "frites, soupe, salade bouillie",
                    1,
                ),
                (
                    "Carottes",
                    ["carottes 1kg", "carottes"],
                    0.75,
                    "Bêta-carotène (pro-vit A, 835 µg/100 g) + fibres solubles + vit K "
                    "— couscous, soupes, salades cuites marocaines, bonne conservation longue durée",
                    1,
                ),
                (
                    "Ail",
                    ["ail 250g", "ail"],
                    0.15,
                    "Allicine antibactérienne + sélénium + manganèse + vit B6 "
                    "— condiment incontournable de toute chermoula, tagine et sauce marocaine",
                    1,
                ),
                (
                    "Herbes fraîches (persil/coriandre)",
                    ["persil coriandre", "persil"],
                    0.3,
                    "Vit K (550 µg/100 g) + vit C + fer + folates + chlorophylle "
                    "— garniture obligatoire de tous les plats marocains, chermoula pour poissons",
                    1,
                ),
                # ── Tomates & condiments de base ───────────────────────────────
                (
                    "Concentré de tomates",
                    ["double concentré tomate", "concentré tomate"],
                    0.5,
                    "Lycopène concentré (10× tomate fraîche) + vit C + fer + zinc "
                    "— base de coloration et saveur de tous les tajines et plats en sauce",
                    1,
                ),
                (
                    "Harissa",
                    ["harissa aïcha forte", "harissa aïcha", "harissa"],
                    0.5,
                    "Vit C (100 mg/100 g) + bêta-carotène + fer + capsaïcine anti-inflammatoire "
                    "— condiment national emblématic, accompagne poissons, kefta, merguez",
                    1,
                ),
                # ── Épices de base — âme de la cuisine marocaine ──────────────
                (
                    "Cumin (épice n°1 marocaine)",
                    ["cumin moulu 100g", "cumin"],
                    0.05,
                    "Fer (66 mg/100 g) + manganèse + calcium + antioxydants thymol "
                    "— épice indispensable de kefta, merguez, chermoula, tagines ; "
                    "favorise la digestion, propriétés antifongiques",
                    1,
                ),
                (
                    "Paprika doux",
                    ["paprika doux 100g", "paprika"],
                    0.05,
                    "Vit C + capsanthin (antioxydant) + vit A + vit E "
                    "— colorant et arôme naturel de tous les plats marocains rouges "
                    "(chermoula, kefta, poulet rôti)",
                    1,
                ),
                # ── Thé — rituel quotidien ─────────────────────────────────────
                (
                    "Thé vert / Atay (polyphénols)",
                    ["atay touareg", "thé atay", "atay", "lipton yellow label", "thé lipton"],
                    0.3,
                    "Polyphénols EGCG antioxydants + fluorure + théine — le thé à la menthe "
                    "(atay) est servi 3 à 5 fois/jour : accueil des invités, pause famille, "
                    "rituel social marocain fondamental ; réduit cholestérol et stress",
                    1,
                ),
                # ── Sucre ──────────────────────────────────────────────────────
                (
                    "Sucre",
                    ["sucre cosumar 1kg", "sucre cosumar", "sucre"],
                    0.4,
                    "Glucides simples — sucrage du thé (3–4 morceaux/verre, 10–15 verres/foyer/jour), "
                    "pâtisseries marocaines (cornes de gazelle, chebakia, ktaïf), confiture",
                    1,
                ),
                # ── Sardines en boîte ──────────────────────────────────────────
                (
                    "Sardines en boîte (protéines + oméga-3)",
                    ["sardines aïcha", "sardines saupiquet", "sardine"],
                    1.5,
                    "Protéines complètes (25 g/100 g) + oméga-3 DHA/EPA (2 g/boîte) "
                    "+ calcium (351 mg) + vit D + sélénium "
                    "— protéine conservée la plus consommée au Maroc ; sandwich sardines, "
                    "salade marocaine, garniture tagine ; longue DLC et prix accessible",
                    1,
                ),
                # ── Lait ───────────────────────────────────────────────────────
                (
                    "Lait (petit-déjeuner marocain)",
                    ["lait uht entier", "lait demi", "lait uht", "jaouda lait",
                     "centrale lait", "lait"],
                    2.0,
                    "Protéines (3,2 g/100 ml) + calcium (120 mg/100 ml) + vit B12 + vit D "
                    "— pilier du petit-déjeuner marocain : café au lait, lait chaud avec pain, "
                    "baghrir ; croissance ossatoire des enfants",
                    1,
                ),

                # ══════════════════════════════════════════════════════════════
                # NIVEAU 2 — NUTRITION ÉQUILIBRÉE
                # Couverture complète des 5 groupes alimentaires,
                # légumes variés, fruits frais, volaille (150–350 DH/pers/sem)
                # ══════════════════════════════════════════════════════════════

                # ── Couscous ───────────────────────────────────────────────────
                (
                    "Couscous (plat national du vendredi)",
                    ["couscous dari", "couscous"],
                    0.4,
                    "Glucides + fibres (2,4 g/100 g) + magnésium + sélénium "
                    "— plat national servi chaque vendredi en famille, "
                    "accompagne agneau, poulet, légumes du jardin ; symbole de partage",
                    2,
                ),
                # ── Pain de mie & biscottes (petit-déjeuner) ──────────────────
                (
                    "Pain de mie (sandwich, snack)",
                    ["pain de mie complet", "pain de mie blanc", "pain de mie"],
                    0.3,
                    "Glucides + fibres (si complet) + vit B — alternative pratique au khobz "
                    "pour sandwiches, toasts du matin, goûters enfants ; "
                    "tartiné de confiture, beurre ou fromage fondu",
                    2,
                ),
                # ── Pâtes ──────────────────────────────────────────────────────
                (
                    "Pâtes alimentaires",
                    ["spaghetti safra", "penne safra", "spaghetti", "penne"],
                    0.5,
                    "Glucides complexes + protéines végétales (13 g/100 g) + vit B "
                    "— repas économique et rapide, bases de plats en sauce tomate marocaine",
                    2,
                ),
                # ── Vermicelles ────────────────────────────────────────────────
                (
                    "Vermicelles (harira, soupe)",
                    ["vermicelles safra", "vermicelles"],
                    0.2,
                    "Glucides légers + satiété — ingrédient indispensable de la harira "
                    "(soupe nationale servie à l'iftar pendant Ramadan), "
                    "aussi utilisés en soupe au lait (hrira beida)",
                    2,
                ),
                # ── Riz ────────────────────────────────────────────────────────
                (
                    "Riz",
                    ["riz long", "riz basmati", "riz"],
                    0.25,
                    "Glucides digestibles + vit B + magnésium + sans gluten "
                    "— riz au lait marocain (roz bel hlib), accompagnement poulet rôti, "
                    "couscous de riz (rfissa), alternative au blé pour intolérants",
                    2,
                ),
                # ── Haricots blancs / Fèves ─────────────────────────────────────
                (
                    "Haricots blancs (loubia)",
                    ["haricots blancs secs", "haricots blancs"],
                    0.3,
                    "Protéines végétales (22 g/100 g) + fibres (11 g) + potassium + folates "
                    "— loubia (haricots blancs en sauce tomate) : plat réconfortant économique, "
                    "très apprécié en hiver avec khobz",
                    2,
                ),
                (
                    "Fèves séchées (bissara)",
                    ["fèves séchées bissara", "feves séchées", "feves bissara"],
                    0.2,
                    "Protéines (26 g/100 g) + fer (6,7 mg) + fibres + acide folique "
                    "— bissara (soupe de fèves à l'huile d'olive, cumin, paprika) : "
                    "plat national de rue (l-bessara), servi au petit-déjeuner dans tout le Maroc",
                    2,
                ),
                # ── Yaourt ─────────────────────────────────────────────────────
                (
                    "Yaourt (probiotiques)",
                    ["yaourt nature danone", "yaourt activia", "yaourt danone",
                     "yaourt", "activia"],
                    1.0,
                    "Probiotiques lactobacilles + calcium (180 mg/pot) + protéines (5 g) + vit B2 "
                    "— flore intestinale, digestion, collation enfants et adultes ; "
                    "aussi base du raïb marocain (lait caillé épaissi)",
                    2,
                ),
                # ── Thon ───────────────────────────────────────────────────────
                (
                    "Thon en boîte",
                    ["thon en boîte", "thon saupiquet", "thon"],
                    0.5,
                    "Protéines maigres (26 g/100 g) + oméga-3 + sélénium (76 µg) + vit B12 "
                    "— salade niçoise marocaine, sandwich, pizza marocaine (matlou farci)",
                    2,
                ),
                # ── Beurre / Margarine ─────────────────────────────────────────
                (
                    "Beurre / Margarine (tartines & msemen)",
                    ["beurre président", "margarine fleurial", "beurre", "margarine"],
                    0.2,
                    "Acides gras + vit A (rétinol) + vit D + vit E "
                    "— tartines du petit-déjeuner, msemen beurré (crêpe feuilletée marocaine), "
                    "briouates, cornes de gazelle ; énergie concentrée pour enfants",
                    2,
                ),
                # ── Fromage ────────────────────────────────────────────────────
                (
                    "Fromage fondu / Fromage blanc",
                    ["fromage blanc danone", "fromage raibi jaouda", "fromage fondu",
                     "vache qui rit", "kiri"],
                    0.5,
                    "Calcium (200 mg/portion) + protéines + vit A + vit B12 "
                    "— tartines avec pain ou biscottes, goûters enfants ; "
                    "La Vache Qui Rit est un produit emblématique depuis des décennies au Maroc",
                    2,
                ),
                # ── Sardines fraîches ──────────────────────────────────────────
                (
                    "Sardines fraîches (poisson du quotidien)",
                    ["sardines fraîches 1kg", "sardines fraîches"],
                    0.5,
                    "Protéines complètes (20 g/100 g) + oméga-3 (2,5 g/100 g) "
                    "+ calcium + phosphore + vit D + vit B12 "
                    "— Maroc = 1ᵉʳ exportateur mondial de sardines (70 % de la pêche nationale) ; "
                    "cuites au chermoula, grillées, farcies, en tagine ; prix très accessible",
                    2,
                ),
                # ── Légumes variés ─────────────────────────────────────────────
                (
                    "Courgettes (tagines d'été)",
                    ["courgettes 1kg", "courgettes"],
                    0.5,
                    "Vit C + manganèse + folates + faibles calories (17 kcal/100 g) "
                    "— tagine de courgettes au poulet, couscous d'été, djaj bil koucha",
                    2,
                ),
                (
                    "Poivrons (taktouka, zaalouk)",
                    ["poivrons 1kg", "poivrons"],
                    0.4,
                    "Vit C (128 mg/100 g = 2× orange) + bêta-carotène + vit B6 + folates "
                    "— taktouka (salade grillée emblématique), chakchouka, chermoula de poivrons",
                    2,
                ),
                (
                    "Aubergines (zaalouk)",
                    ["aubergines 1kg", "aubergines"],
                    0.4,
                    "Fibres (3 g/100 g) + potassium + nasunine antioxydant + manganèse "
                    "— zaalouk (salade d'aubergines grillées à l'huile d'olive) : "
                    "entrée marocaine incontournable, aussi tagine d'aubergines à la tomate",
                    2,
                ),
                (
                    "Légumes verts (épinards, haricots)",
                    ["epinards frais", "haricots verts"],
                    0.5,
                    "Fer non-héminique + vit K + folates (600 µg/100 g épinards) "
                    "+ magnésium + calcium végétal "
                    "— bourreks aux épinards, tagine de haricots, apport en folates essentiel "
                    "pour femmes enceintes",
                    2,
                ),
                # ── Fruits frais ───────────────────────────────────────────────
                (
                    "Oranges / Agrumes (jus matinal)",
                    ["oranges 1kg", "clémentines 1kg", "oranges", "clémentines"],
                    1.0,
                    "Vit C (53 mg/100 g) + flavonoïdes + folates + potassium "
                    "— jus d'orange pressé le matin (tradition marocaine), "
                    "Maroc = 3ᵉ exportateur mondial d'agrumes ; absorption du fer ×3",
                    2,
                ),
                (
                    "Bananes (énergie + potassium)",
                    ["bananes 1kg", "bananes"],
                    0.5,
                    "Potassium (358 mg/100 g) + vit B6 + magnésium + tryptophane "
                    "— collation des enfants, énergie rapide avant l'école, "
                    "fruit le plus vendu dans les marchés marocains",
                    2,
                ),
                # ── Épices complémentaires ─────────────────────────────────────
                (
                    "Ras el Hanout (mélange d'épices marocain)",
                    ["ras el hanout", "ras el hanout 100g"],
                    0.05,
                    "Complexe de 27+ épices (cumin, gingembre, curcuma, cannelle, poivre, "
                    "cardamome, noix de muscade…) — indispensable pour tagine d'agneau, "
                    "pastilla, briouates, couscous royal ; patrimoine culinaire marocain",
                    2,
                ),
                (
                    "Gingembre moulu",
                    ["gingembre moulu 100g", "gingembre moulu"],
                    0.05,
                    "Gingérols anti-inflammatoires + shogaols + antioxydants + vit B6 "
                    "— épice fondamentale de tous les tagines marocains : poulet-citron-olives, "
                    "kefta, harira ; propriétés digestives reconnues",
                    2,
                ),
                # ── Olives (table du matin marocain) ───────────────────────────
                (
                    "Olives beldi marinées",
                    ["olives beldi marinées", "olives beldi", "olives"],
                    0.3,
                    "Acides gras mono-insaturés (oléique 73 %) + vit E + polyphénols + fer "
                    "— présentes sur chaque table marocaine au petit-déjeuner et déjeuner, "
                    "accompagnent khobz, sardines et fromage ; tradition millénaire berbère",
                    2,
                ),
                # ── Confiture (petit-déjeuner) ─────────────────────────────────
                (
                    "Confiture (tartines du matin)",
                    ["confiture abricot aïcha", "confiture fraise aïcha",
                     "confiture aïcha", "confiture"],
                    0.2,
                    "Sucres + vit C (si abricot) + pectines (fibres) "
                    "— tartinée sur khobz ou pain de mie avec beurre : "
                    "petit-déjeuner traditionnel marocain (ftor) ; confiture d'abricot marocaine réputée",
                    2,
                ),
                # ── Café ───────────────────────────────────────────────────────
                (
                    "Café (nhar ou nous-nous)",
                    ["nescafé classic", "café soluble nescafé", "nescafé",
                     "café amara", "café soluble"],
                    0.15,
                    "Magnésium + polyphénols chlorogéniques + caféine (stimulant cognitif) "
                    "— le 'nous-nous' (moitié café, moitié lait chaud) est servi dans chaque café "
                    "marocain dès 6h ; boisson du matin dans de nombreux foyers",
                    2,
                ),
                # ── Volaille — viande principale des foyers ────────────────────
                (
                    "Cuisses de poulet halal (tagine)",
                    ["cuisses de poulet halal", "poulet entier halal",
                     "blancs de poulet halal", "cuisses de poulet"],
                    0.75,
                    "Protéines complètes (25 g/100 g) + vit B3/B6/B12 + zinc + sélénium "
                    "— viande la plus consommée au Maroc (60 % de la viande totale) ; "
                    "tagine poulet-citrons-olives, djaj mqalli, pastilla, rfissa ; "
                    "moins cher que la viande rouge, faible en graisses saturées",
                    2,
                ),

                # ══════════════════════════════════════════════════════════════
                # NIVEAU 3 — PANIER CONFORTABLE ET COMPLET
                # Diversité maximale, viandes rouges, poissons nobles,
                # fruits secs, miel, épices premium (> 350 DH/pers/sem)
                # ══════════════════════════════════════════════════════════════

                # ── Pommes ─────────────────────────────────────────────────────
                (
                    "Pommes (collation & dessert)",
                    ["pommes 1kg", "pommes"],
                    0.5,
                    "Quercétine + catéchines + fibres pectines (2,4 g/100 g) + vit C "
                    "— collation saine, tarte aux pommes marocaine, smoothies, "
                    "bonne conservation ; fruit toute saison",
                    3,
                ),
                # ── Dattes / fruits secs ────────────────────────────────────────
                (
                    "Dattes medjool (fruit emblématique)",
                    ["dattes medjool", "dattes"],
                    0.2,
                    "Sucres naturels (75 g/100 g) + fibres (7 g) + potassium + magnésium + fer "
                    "— rupture du jeûne (ftour du Ramadan), offertes aux invités, "
                    "Maroc = 4ᵉ producteur mondial ; énergie concentrée, antioxydants",
                    3,
                ),
                # ── Miel — patrimoine marocain ──────────────────────────────────
                (
                    "Miel (table du matin & médecine)",
                    ["miel d'euphorbe", "miel de thym", "miel"],
                    0.1,
                    "Fructose + glucose + enzymes (diastase, invertase) + polyphénols "
                    "+ propolis antibactérien + acide gluconique "
                    "— tartiné sur khobz ou msemen : présent sur toute table marocaine, "
                    "utilisé en remède naturel (toux, plaies) ; miel d'euphorbe marocain réputé mondialement",
                    3,
                ),
                # ── Amlou ──────────────────────────────────────────────────────
                (
                    "Amlou (pâte amande-argan berbère)",
                    ["amlou pâte amande", "amlou"],
                    0.1,
                    "Acides gras oméga-9 (huile d'argan) + vit E (200 mg/100 g) + protéines "
                    "d'amande (21 g) + phytostérols + tocophérols antioxydants "
                    "— spécialité berbère du Souss, tartiné sur khobz ou msemen ; "
                    "exporté mondialement, patrimoine culinaire immatériel marocain",
                    3,
                ),
                # ── Citrons confits ─────────────────────────────────────────────
                (
                    "Citrons confits (tagines & poulet)",
                    ["citrons confits bocal", "citrons confits"],
                    0.1,
                    "Vit C + bioflavonoïdes + limonène (anticancer) + acide citrique "
                    "— ingrédient emblématique du tagine poulet-citrons-olives (plat marocain le plus connu), "
                    "khlii, méchoui marinés ; se conservent 6 mois, fait maison ou acheté",
                    3,
                ),
                # ── Épices premium ──────────────────────────────────────────────
                (
                    "Curcuma (anti-inflammatoire)",
                    ["curcuma 100g", "curcuma"],
                    0.05,
                    "Curcumine anti-inflammatoire + antioxydant puissant + vit B6 "
                    "— colore les plats en jaune (tagine de poulet, riz au safran, mrouzia) ; "
                    "propriétés anticancéreuses reconnues par l'OMS",
                    3,
                ),
                (
                    "Cannelle moulue (pâtisseries & plats sucrés-salés)",
                    ["cannelle moulue 100g", "cannelle"],
                    0.05,
                    "Cinnamaldéhyde antioxydant + régulateur glycémique + manganèse "
                    "— ingrédient clé de la pastilla (pigeon-amandes-sucre-cannelle), "
                    "cornes de gazelle, seffa, mrouzia, thé à la cannelle hivernal",
                    3,
                ),
                (
                    "Safran (or rouge marocain)",
                    ["safran filaments", "safran"],
                    0.05,
                    "Safranal (antidépresseur naturel, aussi efficace que la fluoxétine) "
                    "+ crocine antioxydante + vit B2 + manganèse "
                    "— Maroc (Taliouine) = 2ᵉ producteur mondial ; tagine de poulet au safran, "
                    "riz au safran, sauces royales ; patrimoine agricole marocain",
                    3,
                ),
                (
                    "Poivre noir",
                    ["poivre noir moulu 100g", "poivre noir"],
                    0.05,
                    "Pipérine (augmente biodisponibilité curcumine ×2000%) + antioxydants "
                    "— condiment universel, essentiel avec le cumin dans la chermoula et kefta",
                    3,
                ),
                # ── Jus de fruits (vit C + absorption du fer) ──────────────────
                (
                    "Jus d'orange (vit C biodisponible)",
                    ["jus d'orange rajo", "rajo jus", "rajo", "jus d'orange"],
                    0.5,
                    "Vit C (50 mg/100 ml) + potassium + folates + flavonoïdes "
                    "— multiplie l'absorption du fer non-héminique (légumineuses) par 3 ; "
                    "servi au petit-déjeuner ou avec les repas",
                    3,
                ),
                # ── Viande rouge ────────────────────────────────────────────────
                (
                    "Viande hachée / Kefta bœuf halal",
                    ["viande hachée bœuf", "kefta bœuf halal",
                     "viande hachée", "kefta bœuf", "kefta"],
                    0.4,
                    "Protéines complètes (20 g/100 g) + fer héminique (2,5 mg) "
                    "+ zinc (4,8 mg) + vit B12 + créatine "
                    "— kefta grillé (brochettes), kefta mkaouara (œufs en sauce tomate), "
                    "farce briouates et cigares ; plat familial hebdomadaire",
                    3,
                ),
                (
                    "Merguez bœuf halal (week-end)",
                    ["merguez bœuf halal", "merguez bœuf", "merguez"],
                    0.2,
                    "Protéines (18 g/100 g) + fer héminique + zinc + épices (cumin, paprika, harissa) "
                    "— grillées au barbecue le vendredi/weekend, accompagnées de pain et harissa ; "
                    "plat convivial familial marocain",
                    3,
                ),
                (
                    "Agneau halal (couscous du vendredi & méchoui)",
                    ["côtelettes agneau", "escalope de veau", "agneau"],
                    0.2,
                    "Protéines (25 g/100 g) + acides gras mono-insaturés + zinc (4,2 mg) "
                    "+ fer héminique + vit B12 + sélénium "
                    "— couscous royal du vendredi avec légumes (plat symbolique), méchoui, "
                    "tagine d'agneau aux pruneaux et amandes ; consommé 1–2×/semaine",
                    3,
                ),
                (
                    "Dinde hachée / Foie de volaille",
                    ["dinde hachée halal", "foie de poulet", "dinde hachée"],
                    0.3,
                    "Protéines maigres (28 g/100 g) + fer héminique (foie : 8 mg) "
                    "+ vit A (foie : 4 968 µg/100 g) + vit B12 "
                    "— alternative économique au bœuf, kefta de dinde, msemen farci ; "
                    "foie de poulet : abat le plus consommé au Maroc, grillé ou en sauce",
                    3,
                ),
                # ── Poisson noble ───────────────────────────────────────────────
                (
                    "Sole / Crevettes (poisson noble)",
                    ["sole fraîche 1kg", "crevettes fraîches",
                     "sole fraîche", "crevettes"],
                    0.2,
                    "Protéines maigres (20 g/100 g) + oméga-3 DHA + iode + sélénium + zinc "
                    "— tagine de poisson (chermoula-citrons-olives), crevettes grillées ; "
                    "repas du vendredi traditionnel, bonne source d'iode pour la thyroïde",
                    3,
                ),
                # ── Huile d'olive extra vierge ──────────────────────────────────
                (
                    "Huile d'olive extra vierge",
                    ["huile d'olive extra vierge", "moulins de la médina",
                     "huile d'olive", "olive extra"],
                    0.15,
                    "Acide oléique oméga-9 (73 %) + polyphénols (oleuropéine) + vit E + vit K "
                    "— pilier du régime méditerranéen, assaisonnement zaalouk, salade marocaine, "
                    "bissara ; Maroc = 5ᵉ producteur mondial d'huile d'olive",
                    3,
                ),
            ]

            # Plan hygiène — quantités par foyer (semi-linéaires avec le nb de personnes)
            # Facteur: ×1.0 pour ≤2 pers, ×1.5 pour 3-4 pers, ×2.0 pour 5-6 pers
            hyg_factor = (
                1.0 if household_size <= 2
                else 1.5 if household_size <= 4
                else 2.0
            )
            # (rôle, keywords, qté/semaine, justification, niveau_min)
            HYGIENE_PLAN: list[tuple[str, list[str], float, str, int]] = [
                (
                    "Savon (hygiène corporelle)",
                    ["savon dove", "gel douche fa", "dove beauty", "gel douche", "savon"],
                    1.0,
                    "Hygiène corporelle essentielle — élimination bactéries cutanées, "
                    "prévention maladies infectieuses ; 1 savon/sem minimum par foyer",
                    1,
                ),
                (
                    "Lessive",
                    ["lessive tide", "tide 1kg", "lessive omo", "omo 1kg", "lessive"],
                    0.5,
                    "Hygiène du linge — élimination allergènes, bactéries, champignons ; "
                    "indispensable pour nettoyer les djellabas, serviettes, vêtements d'enfants",
                    1,
                ),
                (
                    "Liquide vaisselle",
                    ["liquide vaisselle paic", "paic", "vaisselle"],
                    0.5,
                    "Hygiène alimentaire — dégraissage et élimination agents pathogènes "
                    "sur tajines, cocottes, assiettes et ustensiles",
                    1,
                ),
                (
                    "Eau de Javel (désinfection)",
                    ["eau de javel ajax", "javel ajax", "ajax javel", "ajax"],
                    0.3,
                    "Désinfection des surfaces — élimination virus, bactéries, champignons ; "
                    "cuisine, WC, sol, garde-manger ; dilution 1/20 pour usage courant",
                    1,
                ),
                (
                    "Dentifrice (fluor)",
                    ["dentifrice colgate", "colgate triple", "colgate", "dentifrice"],
                    0.3,
                    "Fluor 1 450 ppm — prévention des caries (−40 %) et maladies parodontales ; "
                    "2× brossage/jour, 2 min ; prévalence caries élevée au Maroc (87 % enfants)",
                    2,
                ),
                (
                    "Shampooing",
                    ["shampooing pantene", "pantene pro", "head & shoulders",
                     "shampooing head", "shampooing"],
                    0.3,
                    "Hygiène du cuir chevelu — élimination sébum, pellicules et pollution ; "
                    "2-3× /semaine ; soin des cheveux important dans la culture marocaine",
                    2,
                ),
                (
                    "Papier Toilette",
                    ["papier toilette lotus", "lotus 8", "lotus", "papier toilette"],
                    0.25,
                    "Hygiène sanitaire de base — 8 rouleaux / mois / foyer ; "
                    "utilisé en complément de la toilette à l'eau (tradition marocaine)",
                    2,
                ),
                (
                    "Déodorant",
                    ["déodorant nivea", "nivea roll", "déodorant"],
                    0.3,
                    "Hygiène corporelle — contrôle transpiration et odeurs ; "
                    "formule 48 h ; usage quotidien dans les foyers urbains",
                    3,
                ),
            ]

            # ── Charger tous les produits actifs avec meilleur prix ───────────
            subq = (
                select(
                    Price.product_id,
                    sqlfunc.min(Price.price).label("min_price"),
                    Price.store_id,
                    Price.is_promo,
                )
                .group_by(Price.product_id, Price.store_id, Price.is_promo)
                .subquery()
            )
            stmt = (
                select(Product, subq.c.min_price, subq.c.store_id, subq.c.is_promo)
                .join(subq, subq.c.product_id == Product.id)
                .where(Product.is_active == True)
            )
            rows = (await db.execute(stmt)).all()

            # Index product_id → meilleur prix toutes sources confondues
            best_prices: dict[int, dict] = {}
            for prod, min_price, store_id, is_promo in rows:
                if prod.id not in best_prices or float(min_price) < best_prices[prod.id]["price"]:
                    best_prices[prod.id] = {
                        "product": prod,
                        "price": float(min_price),
                        "store_id": store_id,
                        "is_promo": bool(is_promo),
                    }

            # Cache noms de magasins
            store_name_cache: dict[int, str] = {}

            async def get_store_name(sid: int) -> str:
                if sid not in store_name_cache:
                    s = await db.get(Store, sid)
                    store_name_cache[sid] = s.name if s else "?"
                return store_name_cache[sid]

            # Cherche le produit le moins cher correspondant aux keywords.
            # Les keywords sont traités par ordre de priorité décroissante :
            # le premier keyword qui donne au moins 1 résultat est utilisé ;
            # on ne passe au keyword suivant que si aucun produit ne matche.
            # Cela évite qu'un keyword générique ("poulet") capture un produit
            # non souhaité ("Foie de Poulet") parce qu'il est moins cher.
            used_pids: set[int] = set()

            def find_best_match(keywords: list[str]) -> dict | None:
                for kw in keywords:
                    kw_l = kw.lower()
                    candidates = [
                        info for pid, info in best_prices.items()
                        if pid not in used_pids and kw_l in info["product"].name.lower()
                    ]
                    if candidates:
                        return min(candidates, key=lambda x: x["price"])
                return None

            # ── Table de catégorisation par mots-clés dans le nom produit ────────
            # Chaque entrée : (fragment_nom_lower, catégorie_affichage)
            # Parcourue dans l'ordre — premier match retenu.
            CATEGORY_RULES: list[tuple[str, str]] = [
                # Eau & Boissons
                ("eau min",          "💧 Eau & Boissons"),
                ("sidi ali",         "💧 Eau & Boissons"),
                ("bahia",            "💧 Eau & Boissons"),
                ("jus d'orange",     "💧 Eau & Boissons"),
                ("jus ",             "💧 Eau & Boissons"),
                ("coca-cola",        "💧 Eau & Boissons"),
                ("pepsi",            "💧 Eau & Boissons"),
                ("lipton ice",       "💧 Eau & Boissons"),
                ("rajo",             "💧 Eau & Boissons"),
                ("raibi jaouda 1l",  "💧 Eau & Boissons"),
                # Pain & Céréales
                ("farine",           "🌾 Pain & Céréales"),
                ("levure",           "🌾 Pain & Céréales"),
                ("pain de mie",      "🌾 Pain & Céréales"),
                ("biscottes",        "🌾 Pain & Céréales"),
                ("couscous",         "🌾 Pain & Céréales"),
                ("spaghetti",        "🌾 Pain & Céréales"),
                ("penne",            "🌾 Pain & Céréales"),
                ("vermicelles",      "🌾 Pain & Céréales"),
                ("riz ",             "🌾 Pain & Céréales"),
                # Œufs
                ("oeufs frais",      "🥚 Œufs"),
                # Légumineuses
                ("pois chiches",     "🫘 Légumineuses"),
                ("lentilles",        "🫘 Légumineuses"),
                ("haricots blancs",  "🫘 Légumineuses"),
                ("fèves",            "🫘 Légumineuses"),
                # Légumes frais
                ("tomates fraîches", "🥦 Légumes & Herbes"),
                ("oignons",          "🥦 Légumes & Herbes"),
                ("pommes de terre",  "🥦 Légumes & Herbes"),
                ("carottes",         "🥦 Légumes & Herbes"),
                ("courgettes",       "🥦 Légumes & Herbes"),
                ("poivrons",         "🥦 Légumes & Herbes"),
                ("aubergines",       "🥦 Légumes & Herbes"),
                ("navets",           "🥦 Légumes & Herbes"),
                ("chou blanc",       "🥦 Légumes & Herbes"),
                ("epinards",         "🥦 Légumes & Herbes"),
                ("haricots verts",   "🥦 Légumes & Herbes"),
                ("betteraves",       "🥦 Légumes & Herbes"),
                ("petits pois",      "🥦 Légumes & Herbes"),
                ("persil",           "🥦 Légumes & Herbes"),
                ("ail ",             "🥦 Légumes & Herbes"),
                # Fruits frais
                ("oranges",          "🍊 Fruits frais"),
                ("pommes 1kg",       "🍊 Fruits frais"),
                ("bananes",          "🍊 Fruits frais"),
                ("clémentines",      "🍊 Fruits frais"),
                ("grenades",         "🍊 Fruits frais"),
                ("raisins 1kg",      "🍊 Fruits frais"),
                ("pastèque",         "🍊 Fruits frais"),
                ("dattes",           "🍊 Fruits frais"),
                ("figues",           "🍊 Fruits frais"),
                # Poissons & fruits de mer
                ("sardines fraîches","🐟 Poissons & Fruits de mer"),
                ("sardines",         "🐟 Poissons & Fruits de mer"),
                ("thon",             "🐟 Poissons & Fruits de mer"),
                ("sole fraîche",     "🐟 Poissons & Fruits de mer"),
                ("crevettes",        "🐟 Poissons & Fruits de mer"),
                # Volaille halal
                ("poulet",           "🍗 Volaille (halal)"),
                ("cuisses",          "🍗 Volaille (halal)"),
                ("blancs de poulet", "🍗 Volaille (halal)"),
                ("dinde",            "🍗 Volaille (halal)"),
                ("foie de poulet",   "🍗 Volaille (halal)"),
                # Viande rouge halal
                ("viande hachée",    "🥩 Viande rouge (halal)"),
                ("kefta",            "🥩 Viande rouge (halal)"),
                ("merguez",          "🥩 Viande rouge (halal)"),
                ("agneau",           "🥩 Viande rouge (halal)"),
                ("escalope de veau", "🥩 Viande rouge (halal)"),
                ("côtelettes",       "🥩 Viande rouge (halal)"),
                # Produits laitiers
                ("lait uht",         "🥛 Produits laitiers"),
                ("lait 1er",         "🥛 Produits laitiers"),
                ("yaourt",           "🥛 Produits laitiers"),
                ("activia",          "🥛 Produits laitiers"),
                ("fromage",          "🥛 Produits laitiers"),
                ("vache qui rit",    "🥛 Produits laitiers"),
                ("kiri",             "🥛 Produits laitiers"),
                ("raibi jaouda 5",   "🥛 Produits laitiers"),
                ("crème fraîche",    "🥛 Produits laitiers"),
                # Huiles & Corps gras
                ("huile de tournesol","🫒 Huiles & Corps gras"),
                ("huile de soja",    "🫒 Huiles & Corps gras"),
                ("huile d'olive",    "🫒 Huiles & Corps gras"),
                ("beurre",           "🫒 Huiles & Corps gras"),
                ("margarine",        "🫒 Huiles & Corps gras"),
                # Boissons chaudes & Sucre
                ("thé atay",         "🍵 Thé, Café & Sucre"),
                ("atay touareg",     "🍵 Thé, Café & Sucre"),
                ("lipton yellow",    "🍵 Thé, Café & Sucre"),
                ("nescafé",          "🍵 Thé, Café & Sucre"),
                ("café amara",       "🍵 Thé, Café & Sucre"),
                ("café soluble",     "🍵 Thé, Café & Sucre"),
                ("sucre cosumar",    "🍵 Thé, Café & Sucre"),
                # Épicerie : épices & condiments
                ("sel fin",          "🧂 Épices & Condiments"),
                ("cumin",            "🧂 Épices & Condiments"),
                ("paprika",          "🧂 Épices & Condiments"),
                ("ras el hanout",    "🧂 Épices & Condiments"),
                ("gingembre",        "🧂 Épices & Condiments"),
                ("curcuma",          "🧂 Épices & Condiments"),
                ("cannelle",         "🧂 Épices & Condiments"),
                ("safran",           "🧂 Épices & Condiments"),
                ("poivre noir",      "🧂 Épices & Condiments"),
                ("harissa",          "🧂 Épices & Condiments"),
                ("concentré tomate", "🧂 Épices & Condiments"),
                ("double concentré", "🧂 Épices & Condiments"),
                ("tomates pelées",   "🧂 Épices & Condiments"),
                ("olives",           "🧂 Épices & Condiments"),
                ("citrons confits",  "🧂 Épices & Condiments"),
                # Petit-déjeuner marocain (ftor)
                ("miel",             "🍯 Petit-déjeuner marocain"),
                ("amlou",            "🍯 Petit-déjeuner marocain"),
                ("confiture",        "🍯 Petit-déjeuner marocain"),
                ("biscottes",        "🍯 Petit-déjeuner marocain"),
                # Hygiène & Entretien (catchall)
                ("savon",            "🧴 Hygiène & Entretien"),
                ("gel douche",       "🧴 Hygiène & Entretien"),
                ("dentifrice",       "🧴 Hygiène & Entretien"),
                ("shampooing",       "🧴 Hygiène & Entretien"),
                ("lessive",          "🧴 Hygiène & Entretien"),
                ("liquide vaisselle","🧴 Hygiène & Entretien"),
                ("eau de javel",     "🧴 Hygiène & Entretien"),
                ("papier toilette",  "🧴 Hygiène & Entretien"),
                ("déodorant",        "🧴 Hygiène & Entretien"),
                ("nettoyant wc",     "🧴 Hygiène & Entretien"),
                ("canard",           "🧴 Hygiène & Entretien"),
                ("paic",             "🧴 Hygiène & Entretien"),
                ("tide",             "🧴 Hygiène & Entretien"),
                ("omo",              "🧴 Hygiène & Entretien"),
                ("pantene",          "🧴 Hygiène & Entretien"),
                ("colgate",          "🧴 Hygiène & Entretien"),
                ("nivea",            "🧴 Hygiène & Entretien"),
                ("dove",             "🧴 Hygiène & Entretien"),
                ("ajax",             "🧴 Hygiène & Entretien"),
                ("lotus",            "🧴 Hygiène & Entretien"),
                # Bébé
                ("pampers",          "👶 Bébé"),
                ("blédina",          "👶 Bébé"),
                ("waterwipes",       "👶 Bébé"),
            ]

            def resolve_category(product_name: str) -> str:
                n = product_name.lower()
                for fragment, cat in CATEGORY_RULES:
                    if fragment in n:
                        return cat
                return "🛒 Divers"

            # Ajoute un article depuis un blueprint entry
            async def add_item(
                keywords: list[str],
                qty_per_pers_week: float,
                reasoning: str,
                hs: int,
            ) -> bool:
                nonlocal total
                match = find_best_match(keywords)
                if not match:
                    return False
                pid = match["product"].id
                raw = qty_per_pers_week * hs * weeks
                qty = max(1, round(raw))
                unit_price = match["price"]
                line_total = round(unit_price * qty, 2)
                # Si dépasse le budget : tenter demi-quantité
                if budget_max and (total + line_total) > budget_max:
                    qty = max(1, qty // 2)
                    line_total = round(unit_price * qty, 2)
                    if total + line_total > budget_max:
                        return False
                sname = await get_store_name(match["store_id"])
                used_pids.add(pid)
                items.append(GeneratedListItem(
                    product_name=match["product"].name,
                    product_id=pid,
                    quantity=float(qty),
                    unit=match["product"].unit,
                    estimated_price_unit=unit_price,
                    estimated_price_total=line_total,
                    store_id=match["store_id"],
                    store_name=sname,
                    is_promo=match["is_promo"],
                    reasoning=reasoning,
                    category=resolve_category(match["product"].name),
                ))
                total += line_total
                return True

            # ── Ajouter les articles nutritionnels (filtrés par tier) ──────────
            for _role, kws, qty_base, reason, priority in NUTRITION_PLAN:
                if priority <= tier:
                    await add_item(kws, qty_base, reason, household_size)

            # ── Ajouter les articles hygiène (filtrés par tier) ───────────────
            # Pour l'hygiène, la quantité est modulée par hyg_factor (semi-linéaire)
            eff_hs = max(1, round(household_size * hyg_factor / max(household_size, 1)))
            for _role, kws, qty_base, reason, priority in HYGIENE_PLAN:
                if priority <= tier:
                    await add_item(kws, qty_base, reason, eff_hs)

        # ── Résumé ─────────────────────────────────────────────────────────────
        stores_mentioned = list(dict.fromkeys(
            i.store_name for i in items if i.store_name
        ))[:3]
        n = household_size
        type_label = {
            "hebdo": "semaine",
            "bi-mensuel": "2 semaines",
            "mensuel": "mois",
        }.get(list_type, list_type)

        # ── Résumé nutritionnel ────────────────────────────────────────────────
        hyg_keywords = [
            "Hygiène", "Lessive", "Désinfection", "Fluor", "Déodorant",
            "sanitaire", "pellicules", "WC",
        ]
        hygiene_items = sum(1 for i in items if any(w in i.reasoning for w in hyg_keywords))
        food_items = len(items) - hygiene_items

        # Libellé du niveau de pouvoir d'achat
        tier_label = {
            1: "économique (essentiels absolu)",
            2: "standard (nutrition équilibrée)",
            3: "confortable (panier complet marocain)",
        }.get(tier, "complet")

        tier_description = {
            1: (
                "Panier de base nutritionnellement couvert : "
                "eau, pain/farine, œufs, sardines, légumineuses (harira), légumes de saison, "
                "condiments (ail, harissa, cumin, paprika), thé, sucre et hygiène essentielle."
            ),
            2: (
                "Panier équilibré couvrant les 7 groupes alimentaires : "
                "glucides (couscous, pâtes, pain), protéines (poulet halal, sardines, œufs, lait, yaourt), "
                "légumes variés (zaalouk, tagine, harira), fruits frais (agrumes, bananes), "
                "légumineuses (pois chiches, lentilles, haricots), condiments et épices marocaines, "
                "olives et confiture pour le petit-déjeuner, hygiène corporelle et entretien."
            ),
            3: (
                "Panier complet adapté à la culture culinaire marocaine : "
                "tous les groupes alimentaires, viandes halal (poulet, kefta, merguez, agneau du vendredi), "
                "poisson frais, sardines, légumes et fruits de saison, épices complètes "
                "(ras el hanout, safran, gingembre, curcuma, cannelle), "
                "miel, amlou, citrons confits, dattes, huile d'olive, olives, confiture "
                "pour un petit-déjeuner marocain traditionnel (ftor) complet."
            ),
        }.get(tier, "")

        return GeneratedList(
            user_id=user_id,
            list_type=list_type,
            budget_max=budget_max,
            total_estimated=round(total, 2),
            items=items,
            recommended_stores=stores_mentioned,
            budget_status=(
                "dans_budget" if (not budget_max or total <= budget_max)
                else "dépasse_budget"
            ),
            global_reasoning=(
                f"Liste {tier_label} pour {n} personne{'s' if n > 1 else ''} sur 1 {type_label}. "
                f"{tier_description} "
                f"Total : {len(items)} articles "
                f"({food_items} alimentaires · {hygiene_items} hygiène/entretien)."
            ),
            generated_at=datetime.now(timezone.utc),
            claude_model="fallback",
            fallback_mode=True,
        )


# ──────────────────────────────────────────────────────────────────────────────
# PromoAlerter
# ──────────────────────────────────────────────────────────────────────────────

class PromoAlerter:
    """
    Génère des alertes promotions personnalisées.

    Score de pertinence :
        score = purchase_frequency × (1 - promo_price / regular_price)

    Plus la fréquence d'achat est haute ET la remise grande, plus le score est élevé.
    Seuil par défaut : 0.15 (configurable).
    """

    DEFAULT_THRESHOLD = 0.15

    async def get_alerts(
        self,
        user_id: int,
        db: AsyncSession,
        threshold: float = DEFAULT_THRESHOLD,
        window_days: int = 90,
        limit: int = 20,
    ) -> list[PromoAlert]:
        # ── Habitudes utilisateur ─────────────────────────────────────────────
        analyzer = HabitAnalyzer(window_days=window_days)
        habits = await analyzer.analyze(user_id, db)

        if not habits.habits:
            return []

        # Index fréquence par nom + product_id
        freq_by_id: dict[int, float] = {
            h.product_id: h.purchase_frequency
            for h in habits.habits if h.product_id
        }
        freq_by_name: dict[str, tuple[float, PurchaseHabit]] = {
            _normalize_name(h.product_name): (h.purchase_frequency, h)
            for h in habits.habits
        }

        # ── Promotions actives en DB ──────────────────────────────────────────
        subq = (
            select(
                Price.product_id,
                Price.store_id,
                func.max(Price.recorded_at).label("latest"),
            )
            .where(Price.is_promo == True)
            .group_by(Price.product_id, Price.store_id)
            .subquery()
        )
        stmt = (
            select(Price, Product, Store)
            .join(Product, Price.product_id == Product.id)
            .join(Store, Price.store_id == Store.id)
            .join(subq, and_(
                Price.product_id == subq.c.product_id,
                Price.store_id == subq.c.store_id,
                Price.recorded_at == subq.c.latest,
            ))
            .where(
                Price.is_promo == True,
                Price.promo_price != None,
                Product.is_active == True,
                Store.is_active == True,
            )
        )
        result = await db.execute(stmt)

        alerts: list[PromoAlert] = []
        seen: set[tuple[int, int]] = set()

        for price, product, store in result.all():
            key = (product.id, store.id)
            if key in seen:
                continue
            seen.add(key)

            regular = float(price.price)
            promo = float(price.promo_price)
            if regular <= 0 or promo >= regular:
                continue

            discount_ratio = 1 - (promo / regular)
            discount_pct = round(discount_ratio * 100, 1)

            # Cherche la fréquence : d'abord par ID, puis fuzzy par nom
            frequency = freq_by_id.get(product.id, 0.0)
            if frequency == 0.0:
                norm_name = _normalize_name(product.name)
                best_score = 0.0
                for habit_norm, (freq, _habit) in freq_by_name.items():
                    score = _fuzzy_score(norm_name, habit_norm)
                    if score > best_score:
                        best_score = score
                        if score >= 0.75:
                            frequency = freq

            score = round(frequency * discount_ratio, 4)
            if score < threshold:
                continue

            reason_parts = [f"Promo -{discount_pct}% chez {store.name}"]
            if frequency > 0:
                reason_parts.append(
                    f"Vous achetez ce produit {frequency*100:.0f}% des semaines"
                )
            reason_parts.append(
                f"Économie : {round(regular - promo, 2)} MAD par unité"
            )

            alerts.append(PromoAlert(
                product_id=product.id,
                product_name=product.name,
                product_image=product.image_url,
                store_id=store.id,
                store_name=store.name,
                store_city=store.city,
                regular_price=regular,
                promo_price=promo,
                discount_pct=discount_pct,
                purchase_frequency=frequency,
                relevance_score=score,
                reason=" — ".join(reason_parts),
                recorded_at=price.recorded_at,
            ))

        alerts.sort(key=lambda a: a.relevance_score, reverse=True)
        return alerts[:limit]


# ──────────────────────────────────────────────────────────────────────────────
# IAService — façade principale
# ──────────────────────────────────────────────────────────────────────────────

class IAService:
    """
    Façade exposée aux routers FastAPI.

    Usage :
        ia = IAService()
        habits  = await ia.analyze_habits(user_id, db)
        liste   = await ia.generate_list(user_id, "hebdo", 300.0, db, user)
        alerts  = await ia.get_promo_alerts(user_id, db)
    """

    def __init__(self):
        self._analyzer = HabitAnalyzer(window_days=90)
        self._generator = ListGenerator()
        self._alerter = PromoAlerter()

    async def analyze_habits(
        self,
        user_id: int,
        db: AsyncSession,
        window_days: int = 90,
    ) -> UserHabits:
        self._analyzer.window_days = window_days
        return await self._analyzer.analyze(user_id, db)

    async def generate_list(
        self,
        user_id: int,
        list_type: str,
        budget_max: float | None,
        db: AsyncSession,
        user: User | None = None,
        household_size: int = 1,
    ) -> GeneratedList:
        if list_type not in ("hebdo", "bi-mensuel", "mensuel"):
            raise ValueError(f"Type de liste invalide : {list_type}")
        return await self._generator.generate(
            user_id, list_type, budget_max, db, user, household_size
        )

    async def get_promo_alerts(
        self,
        user_id: int,
        db: AsyncSession,
        threshold: float = PromoAlerter.DEFAULT_THRESHOLD,
        limit: int = 20,
    ) -> list[PromoAlert]:
        return await self._alerter.get_alerts(
            user_id, db, threshold=threshold, limit=limit,
        )


# Singleton partagé
ia_service = IAService()
