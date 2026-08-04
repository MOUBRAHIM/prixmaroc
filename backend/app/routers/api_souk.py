"""
Router /api/souk — Prix communautaires du souk (contributions citoyennes).

POST /api/souk/prices            Proposer un prix (légumes/fruits/viande/poisson)
GET  /api/souk/prices            Lister les relevés (filtrable par ville/catégorie)
POST /api/souk/prices/{id}/vote  Voter 👍/👎 sur un relevé
GET  /api/souk/median            Prix médians agrégés par produit et ville
GET  /api/souk/categories        Catégories + suggestions de produits (aide formulaire)
"""
from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.models.souk_price import SoukCategory, SoukPrice, SoukStatus, SoukVote
from app.schemas.souk import (
    SoukCategoryInfo, SoukMedianItem, SoukPriceCreate, SoukPriceRead, SoukVoteCreate,
)
from app.services.souk_moderation import moderate
from app.utils.deps import get_current_user, get_optional_user

router = APIRouter(prefix="/api/souk", tags=["souk"])


# ── Métadonnées catégories (aide au formulaire mobile) ──────────────────────────
_CATEGORY_INFO: list[SoukCategoryInfo] = [
    SoukCategoryInfo(value=SoukCategory.LEGUMES, label="Légumes", icon="🥦",
                     suggestions=["Tomates", "Oignons", "Pommes de terre", "Carottes",
                                  "Courgettes", "Poivrons", "Petits pois", "Haricots verts"]),
    SoukCategoryInfo(value=SoukCategory.FRUITS, label="Fruits", icon="🍊",
                     suggestions=["Oranges", "Bananes", "Pommes", "Fraises", "Raisins",
                                  "Melon", "Pastèque", "Dattes"]),
    SoukCategoryInfo(value=SoukCategory.VIANDE, label="Viande", icon="🥩",
                     suggestions=["Poulet beldi", "Poulet fermier", "Viande hachée bœuf",
                                  "Côtelettes d'agneau", "Kefta", "Foie", "Dinde"]),
    SoukCategoryInfo(value=SoukCategory.POISSON, label="Poisson", icon="🐟",
                     suggestions=["Sardines", "Merlan", "Dorade", "Maquereau",
                                  "Crevettes", "Calamar", "Sole", "Thon"]),
]


def _to_read(sp: SoukPrice, my_vote: int | None = None) -> SoukPriceRead:
    return SoukPriceRead(
        id=sp.id, user_id=sp.user_id,
        contributor=sp.user.username if sp.user else None,
        item_name=sp.item_name, category=sp.category, unit=sp.unit,
        price=float(sp.price), currency=sp.currency, city=sp.city,
        neighborhood=sp.neighborhood, latitude=sp.latitude, longitude=sp.longitude,
        photo_url=sp.photo_url, note=sp.note, status=sp.status,
        moderation_reason=sp.moderation_reason, upvotes=sp.upvotes, downvotes=sp.downvotes,
        my_vote=my_vote, created_at=sp.created_at,
    )


# ── GET /api/souk/categories ────────────────────────────────────────────────────
@router.get("/categories", response_model=list[SoukCategoryInfo],
            summary="Catégories de souk + suggestions de produits")
async def list_categories():
    return _CATEGORY_INFO


# ── POST /api/souk/prices ───────────────────────────────────────────────────────
@router.post("/prices", response_model=SoukPriceRead, status_code=status.HTTP_201_CREATED,
             summary="Proposer un prix de souk (modéré automatiquement)")
async def submit_price(
    payload: SoukPriceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    verdict = await moderate(
        db,
        item_name=payload.item_name.strip(),
        category=payload.category,
        unit=payload.unit,
        price=payload.price,
        city=payload.city.strip(),
    )

    sp = SoukPrice(
        user_id=current_user.id,
        item_name=payload.item_name.strip(),
        category=payload.category,
        unit=payload.unit,
        price=payload.price,
        city=payload.city.strip(),
        neighborhood=(payload.neighborhood or None),
        latitude=payload.latitude,
        longitude=payload.longitude,
        photo_url=payload.photo_url,
        note=payload.note,
        status=verdict.status,
        moderation_reason=verdict.reason,
        moderation_source=verdict.source,
    )
    db.add(sp)
    await db.commit()
    await db.refresh(sp, attribute_names=["user"])
    return _to_read(sp)


# ── GET /api/souk/prices ────────────────────────────────────────────────────────
@router.get("/prices", response_model=list[SoukPriceRead],
            summary="Lister les relevés de prix du souk")
async def list_prices(
    city: str | None = Query(None, description="Filtrer par ville"),
    category: SoukCategory | None = Query(None),
    item_name: str | None = Query(None, description="Filtrer par produit (contient)"),
    include_pending: bool = Query(False, description="Inclure aussi les relevés en attente"),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
):
    stmt = select(SoukPrice).where(SoukPrice.is_active.is_(True))
    if include_pending:
        stmt = stmt.where(SoukPrice.status != SoukStatus.REJECTED)
    else:
        stmt = stmt.where(SoukPrice.status == SoukStatus.APPROVED)
    if city:
        stmt = stmt.where(SoukPrice.city.ilike(city))
    if category:
        stmt = stmt.where(SoukPrice.category == category)
    if item_name:
        stmt = stmt.where(SoukPrice.item_name.ilike(f"%{item_name}%"))
    stmt = stmt.order_by(SoukPrice.created_at.desc()).offset(skip).limit(limit)

    rows = (await db.execute(stmt)).scalars().all()

    # Charger les contributeurs + les votes de l'utilisateur courant
    my_votes: dict[int, int] = {}
    if current_user and rows:
        ids = [r.id for r in rows]
        vstmt = select(SoukVote).where(
            SoukVote.user_id == current_user.id, SoukVote.souk_price_id.in_(ids),
        )
        for v in (await db.execute(vstmt)).scalars().all():
            my_votes[v.souk_price_id] = v.value

    result = []
    for sp in rows:
        await db.refresh(sp, attribute_names=["user"])
        result.append(_to_read(sp, my_votes.get(sp.id)))
    return result


# ── GET /api/souk/median ────────────────────────────────────────────────────────
@router.get("/median", response_model=list[SoukMedianItem],
            summary="Prix médians par produit pour une ville")
async def median_prices(
    city: str = Query(..., description="Ville (obligatoire)"),
    category: SoukCategory | None = Query(None),
    window_days: int = Query(21, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    since = datetime.now(timezone.utc) - timedelta(days=window_days)
    stmt = select(SoukPrice).where(
        SoukPrice.status == SoukStatus.APPROVED,
        SoukPrice.is_active.is_(True),
        SoukPrice.city.ilike(city),
        SoukPrice.created_at >= since,
    )
    if category:
        stmt = stmt.where(SoukPrice.category == category)
    rows = (await db.execute(stmt)).scalars().all()

    # Regrouper par (produit normalisé, unité)
    groups: dict[tuple[str, str], list[SoukPrice]] = defaultdict(list)
    for sp in rows:
        groups[(sp.item_name.strip().lower(), sp.unit)].append(sp)

    out: list[SoukMedianItem] = []
    for (_key, unit), items in groups.items():
        prices = [float(i.price) for i in items]
        latest = max(items, key=lambda i: i.created_at)
        out.append(SoukMedianItem(
            item_name=latest.item_name,
            category=latest.category,
            unit=unit,
            median_price=round(statistics.median(prices), 2),
            min_price=round(min(prices), 2),
            max_price=round(max(prices), 2),
            sample_count=len(prices),
            city=latest.city,
            last_updated=latest.created_at,
        ))
    out.sort(key=lambda m: (m.category.value, m.item_name))
    return out


# ── POST /api/souk/prices/{id}/vote ─────────────────────────────────────────────
@router.post("/prices/{price_id}/vote", response_model=SoukPriceRead,
             summary="Voter sur un relevé (fiable 👍 / douteux 👎)")
async def vote_price(
    price_id: int,
    payload: SoukVoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if payload.value not in (1, -1):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "value doit être +1 ou -1")

    sp = await db.get(SoukPrice, price_id)
    if not sp or not sp.is_active:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relevé introuvable")

    existing = (await db.execute(
        select(SoukVote).where(
            SoukVote.souk_price_id == price_id, SoukVote.user_id == current_user.id,
        )
    )).scalar_one_or_none()

    if existing is None:
        db.add(SoukVote(souk_price_id=price_id, user_id=current_user.id, value=payload.value))
        my_vote = payload.value
    elif existing.value == payload.value:
        # Re-cliquer le même vote → annulation
        await db.delete(existing)
        my_vote = None
    else:
        existing.value = payload.value
        my_vote = payload.value

    await db.flush()

    # Recompter à partir de la source de vérité
    votes = (await db.execute(
        select(SoukVote.value).where(SoukVote.souk_price_id == price_id)
    )).scalars().all()
    sp.upvotes = sum(1 for v in votes if v == 1)
    sp.downvotes = sum(1 for v in votes if v == -1)

    await db.commit()
    await db.refresh(sp, attribute_names=["user"])
    return _to_read(sp, my_vote)
