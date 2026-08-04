"""
Router /api/prices

GET /api/prices/cheapest    Prix le moins cher pour un produit (avec savings)
GET /api/prices/promotions  Promotions en cours (filtre ville / user)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Price, Product, Store
from app.schemas.api import (
    CheapestPrice,
    CheapestResponse,
    PromoItem,
    PromosResponse,
)
from app.utils.cache import (
    TTL_PRICES,
    TTL_SHORT,
    cache,
    make_prices_key,
    make_promotions_key,
)

router = APIRouter(prefix="/api/prices", tags=["prices"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _effective_price(price: Price) -> float:
    if price.is_promo and price.promo_price:
        return float(price.promo_price)
    return float(price.price)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/prices/cheapest
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/cheapest", response_model=CheapestResponse, summary="Prix le moins cher par magasin")
async def get_cheapest(
    product_id: int = Query(..., description="ID du produit"),
    city: str | None = Query(None, description="Filtrer par ville"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = make_prices_key(product_id, city) + ":cheapest"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    product = await db.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    # Sous-requête : prix le plus récent par magasin
    subq = (
        select(
            Price.store_id,
            func.max(Price.recorded_at).label("latest"),
        )
        .where(Price.product_id == product_id)
        .group_by(Price.store_id)
        .subquery()
    )

    stmt = (
        select(Price, Store)
        .join(Store, Price.store_id == Store.id)
        .join(subq, and_(
            Price.store_id == subq.c.store_id,
            Price.recorded_at == subq.c.latest,
        ))
        .where(Price.product_id == product_id, Store.is_active == True)
    )
    if city:
        stmt = stmt.where(Store.city.ilike(f"%{city}%"))

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="Aucun prix disponible pour ce produit")

    entries: list[tuple[float, Price, Store]] = []
    for price, store in rows:
        entries.append((_effective_price(price), price, store))

    entries.sort(key=lambda x: x[0])

    all_effectives = [e[0] for e in entries]
    avg = round(sum(all_effectives) / len(all_effectives), 2)

    results: list[CheapestPrice] = []
    for eff, price, store in entries:
        savings_vs_avg = round(avg - eff, 2) if avg else None
        savings_pct = round((savings_vs_avg / avg) * 100, 1) if savings_vs_avg and avg else None
        results.append(CheapestPrice(
            store_id=store.id,
            store_name=store.name,
            store_city=store.city,
            store_lat=float(store.latitude) if store.latitude else None,
            store_lng=float(store.longitude) if store.longitude else None,
            price=float(price.price),
            is_promo=price.is_promo,
            promo_price=float(price.promo_price) if price.promo_price else None,
            effective_price=eff,
            recorded_at=price.recorded_at,
            savings_vs_avg=savings_vs_avg if savings_vs_avg and savings_vs_avg > 0 else None,
            savings_pct=savings_pct if savings_pct and savings_pct > 0 else None,
        ))

    response = CheapestResponse(
        product_id=product_id,
        product_name=product.name,
        city=city,
        results=results,
        average_price=avg,
    )
    await cache.set(cache_key, response.model_dump(mode="json"), ttl=TTL_PRICES)
    return response


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/prices/promotions
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/promotions", response_model=PromosResponse, summary="Promotions en cours")
async def get_promotions(
    city: str | None = Query(None, description="Filtrer par ville"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    cache_key = make_promotions_key(city) + f":{limit}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Sous-requête : derniers prix par (product, store)
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
        .order_by(desc(
            (func.cast(Price.price, type_=Price.price.type) - func.cast(Price.promo_price, type_=Price.promo_price.type))
            / func.cast(Price.price, type_=Price.price.type)
        ))
        .limit(limit)
    )
    if city:
        stmt = stmt.where(Store.city.ilike(f"%{city}%"))

    result = await db.execute(stmt)
    rows = result.all()

    promotions: list[PromoItem] = []
    for price, product, store in rows:
        regular = float(price.price)
        promo = float(price.promo_price)
        if regular <= 0:
            continue
        discount_pct = round((regular - promo) / regular * 100, 1)
        promotions.append(PromoItem(
            product_id=product.id,
            product_name=product.name,
            product_image=product.image_url,
            store_id=store.id,
            store_name=store.name,
            store_city=store.city,
            regular_price=regular,
            promo_price=promo,
            discount_pct=discount_pct,
            promo_end=None,
            recorded_at=price.recorded_at,
        ))

    response = PromosResponse(city=city, count=len(promotions), promotions=promotions)
    await cache.set(cache_key, response.model_dump(mode="json"), ttl=TTL_SHORT)
    return response
