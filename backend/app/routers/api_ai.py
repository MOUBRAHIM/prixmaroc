"""
Router /api/ai

POST /api/ai/generate-list      Génère une liste de courses personnalisée via Claude
GET  /api/ai/habits             Analyse des habitudes d'achat de l'utilisateur
GET  /api/ai/promo-alerts       Alertes promos personnalisées (score pertinence)
"""
from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.services.ia_service import (
    GeneratedList,
    GeneratedListItem,
    PromoAlert,
    UserHabits,
    ia_service,
)
from app.utils.cache import TTL_SHORT, cache
from app.utils.deps import get_current_user

router = APIRouter(prefix="/api/ai", tags=["ai"])


# ──────────────────────────────────────────────────────────────────────────────
# Schemas de réponse
# ──────────────────────────────────────────────────────────────────────────────

class GenerateListRequest(BaseModel):
    list_type: Literal["hebdo", "bi-mensuel", "mensuel"] = Field(
        default="hebdo",
        description="Période de la liste : hebdo (7j), bi-mensuel (15j), mensuel (30j)",
    )
    budget_max: float | None = Field(
        default=None,
        description="Budget maximum en MAD (optionnel)",
        ge=10,
        le=10_000,
    )
    household_size: int = Field(
        default=1,
        description="Effectif du foyer (nombre de personnes)",
        ge=1,
        le=20,
    )


class GeneratedListItemOut(BaseModel):
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
    category: str = "🛒 Divers"


class GeneratedListOut(BaseModel):
    user_id: int
    list_type: str
    budget_max: float | None
    total_estimated: float
    items: list[GeneratedListItemOut]
    recommended_stores: list[str]
    budget_status: str
    global_reasoning: str
    generated_at: datetime
    claude_model: str
    fallback_mode: bool


class PurchaseHabitOut(BaseModel):
    product_name: str
    product_id: int | None
    purchase_frequency: float
    avg_quantity: float
    avg_price: float
    category: str | None
    is_recurrent: bool
    last_seen: str        # date ISO
    total_purchases: int


class CategoryBudgetOut(BaseModel):
    category: str
    avg_weekly_budget: float
    avg_monthly_budget: float
    promo_sensitivity: float


class UserHabitsOut(BaseModel):
    user_id: int
    analysis_window_days: int
    scan_count: int
    total_avg_weekly_budget: float
    habits: list[PurchaseHabitOut]
    recurrent_count: int
    category_budgets: list[CategoryBudgetOut]
    analyzed_at: datetime


class PromoAlertOut(BaseModel):
    product_id: int
    product_name: str
    product_image: str | None
    store_id: int
    store_name: str
    store_city: str | None
    regular_price: float
    promo_price: float
    discount_pct: float
    purchase_frequency: float
    relevance_score: float
    reason: str
    recorded_at: datetime


# ──────────────────────────────────────────────────────────────────────────────
# Helpers de conversion dataclass → Pydantic
# ──────────────────────────────────────────────────────────────────────────────

def _habits_to_out(h: UserHabits) -> UserHabitsOut:
    return UserHabitsOut(
        user_id=h.user_id,
        analysis_window_days=h.analysis_window_days,
        scan_count=h.scan_count,
        total_avg_weekly_budget=h.total_avg_weekly_budget,
        recurrent_count=len(h.recurrent_products),
        analyzed_at=h.analyzed_at,
        habits=[
            PurchaseHabitOut(
                product_name=p.product_name,
                product_id=p.product_id,
                purchase_frequency=p.purchase_frequency,
                avg_quantity=p.avg_quantity,
                avg_price=p.avg_price,
                category=p.category,
                is_recurrent=p.is_recurrent,
                last_seen=p.last_seen.isoformat(),
                total_purchases=p.total_purchases,
            )
            for p in h.habits
        ],
        category_budgets=[
            CategoryBudgetOut(
                category=cb.category,
                avg_weekly_budget=cb.avg_weekly_budget,
                avg_monthly_budget=cb.avg_monthly_budget,
                promo_sensitivity=cb.promo_sensitivity,
            )
            for cb in h.category_budgets
        ],
    )


def _list_to_out(gl: GeneratedList) -> GeneratedListOut:
    return GeneratedListOut(
        user_id=gl.user_id,
        list_type=gl.list_type,
        budget_max=gl.budget_max,
        total_estimated=gl.total_estimated,
        items=[
            GeneratedListItemOut(
                product_name=i.product_name,
                product_id=i.product_id,
                quantity=i.quantity,
                unit=i.unit,
                estimated_price_unit=i.estimated_price_unit,
                estimated_price_total=i.estimated_price_total,
                store_id=i.store_id,
                store_name=i.store_name,
                is_promo=i.is_promo,
                reasoning=i.reasoning,
                category=i.category,
            )
            for i in gl.items
        ],
        recommended_stores=gl.recommended_stores,
        budget_status=gl.budget_status,
        global_reasoning=gl.global_reasoning,
        generated_at=gl.generated_at,
        claude_model=gl.claude_model,
        fallback_mode=gl.fallback_mode,
    )


def _alert_to_out(a: PromoAlert) -> PromoAlertOut:
    return PromoAlertOut(
        product_id=a.product_id,
        product_name=a.product_name,
        product_image=a.product_image,
        store_id=a.store_id,
        store_name=a.store_name,
        store_city=a.store_city,
        regular_price=a.regular_price,
        promo_price=a.promo_price,
        discount_pct=a.discount_pct,
        purchase_frequency=a.purchase_frequency,
        relevance_score=a.relevance_score,
        reason=a.reason,
        recorded_at=a.recorded_at,
    )


# ──────────────────────────────────────────────────────────────────────────────
# POST /api/ai/generate-list
# ──────────────────────────────────────────────────────────────────────────────

@router.post(
    "/generate-list",
    response_model=GeneratedListOut,
    summary="Générer une liste de courses intelligente via Claude",
    description=(
        "Analyse vos habitudes d'achat depuis les tickets scannés et génère "
        "une liste optimisée avec Claude Sonnet. Si l'API Claude est indisponible, "
        "bascule automatiquement sur un algorithme déterministe (fallback_mode=true)."
    ),
)
async def generate_list(
    payload: GenerateListRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Pas de cache sur generate-list : résultat personnalisé et volatil
    result = await ia_service.generate_list(
        user_id=current_user.id,
        list_type=payload.list_type,
        budget_max=payload.budget_max,
        household_size=payload.household_size,
        db=db,
        user=current_user,
    )
    return _list_to_out(result)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/ai/habits
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/habits",
    response_model=UserHabitsOut,
    summary="Analyse des habitudes d'achat",
    description=(
        "Analyse les tickets de caisse scannés sur les `window_days` derniers jours "
        "et retourne les fréquences d'achat, budgets par catégorie et produits récurrents."
    ),
)
async def get_habits(
    window_days: int = Query(90, ge=7, le=365, description="Fenêtre d'analyse en jours"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = f"prixmaroc:ia:habits:{current_user.id}:{window_days}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    habits = await ia_service.analyze_habits(
        user_id=current_user.id,
        db=db,
        window_days=window_days,
    )
    out = _habits_to_out(habits)
    await cache.set(cache_key, out.model_dump(mode="json"), ttl=TTL_SHORT)
    return out


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/ai/promo-alerts
# ──────────────────────────────────────────────────────────────────────────────

@router.get(
    "/promo-alerts",
    response_model=list[PromoAlertOut],
    summary="Alertes promotions personnalisées",
    description=(
        "Retourne les promotions en cours triées par score de pertinence. "
        "Score = fréquence_achat × (1 - prix_promo/prix_normal). "
        "Seules les alertes dont le score dépasse `threshold` sont retournées."
    ),
)
async def get_promo_alerts(
    threshold: float = Query(
        0.15,
        ge=0.0,
        le=1.0,
        description="Seuil minimum de pertinence (0.0–1.0)",
    ),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    cache_key = f"prixmaroc:ia:promo-alerts:{current_user.id}:{threshold:.2f}:{limit}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    alerts = await ia_service.get_promo_alerts(
        user_id=current_user.id,
        db=db,
        threshold=threshold,
        limit=limit,
    )
    out = [_alert_to_out(a) for a in alerts]
    await cache.set(cache_key, [o.model_dump(mode="json") for o in out], ttl=TTL_SHORT)
    return out
