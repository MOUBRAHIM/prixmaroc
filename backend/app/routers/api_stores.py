"""
Router /api/stores

GET /api/stores/nearby           Magasins proches (lat/lng/radius)
GET /api/stores/{id}/products    Produits d'un magasin avec leurs prix
GET /api/stores/route-optimize   Optimisation de parcours multi-magasins (greedy TSP)
"""
from __future__ import annotations

import math
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Price, Product, Store
from app.schemas.api import (
    RouteOptimizeResponse,
    RouteStop,
    StoreNearby,
    StoreProductSummary,
    Paginated,
    PageMeta,
)
from app.utils.cache import (
    TTL_STORES,
    TTL_PRICES,
    cache,
    make_stores_key,
    make_store_products_key,
)

router = APIRouter(prefix="/api/stores", tags=["stores"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers géographiques
# ──────────────────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Distance Haversine entre deux points (degrés décimaux) en kilomètres."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.asin(math.sqrt(a))


def _effective_price(price: Price) -> float:
    if price.is_promo and price.promo_price:
        return float(price.promo_price)
    return float(price.price)


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/stores  — Liste tous les magasins actifs
# ──────────────────────────────────────────────────────────────────────────────

@router.get("", summary="Liste des magasins")
async def list_stores(
    city: str | None = Query(None, description="Filtrer par ville"),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Store).where(Store.is_active == True)
    if city:
        stmt = stmt.where(Store.city.ilike(f"%{city}%"))
    stmt = stmt.order_by(Store.name).limit(limit)
    result = await db.execute(stmt)
    stores = result.scalars().all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "slug": s.slug,
            "city": s.city,
            "address": s.address,
            "logo_url": s.logo_url,
            "website": s.website,
        }
        for s in stores
    ]


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/stores/nearby
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/nearby", response_model=list[StoreNearby], summary="Magasins à proximité")
async def get_nearby_stores(
    lat: float = Query(..., description="Latitude du point de référence", ge=-90, le=90),
    lng: float = Query(..., description="Longitude du point de référence", ge=-180, le=180),
    radius: float = Query(5.0, description="Rayon de recherche en km", ge=0.1, le=500),
    limit: int = Query(30, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    cache_key = make_stores_key(lat, lng, radius) + f":{limit}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    # Récupère tous les magasins actifs avec coordonnées
    stmt = select(Store).where(
        Store.is_active == True,
        Store.latitude != None,
        Store.longitude != None,
    )
    result = await db.execute(stmt)
    stores = result.scalars().all()

    # Filtre et calcul de distance côté Python (évite l'extension PostGIS)
    nearby: list[dict[str, Any]] = []
    for store in stores:
        dist = _haversine_km(lat, lng, float(store.latitude), float(store.longitude))
        if dist <= radius:
            nearby.append({"store": store, "distance_km": round(dist, 3)})

    nearby.sort(key=lambda x: x["distance_km"])
    nearby = nearby[:limit]

    # Comptage produits par magasin (prix actifs)
    store_ids = [n["store"].id for n in nearby]
    product_counts: dict[int, int] = {}
    if store_ids:
        count_stmt = (
            select(Price.store_id, func.count(Price.product_id.distinct()).label("cnt"))
            .where(Price.store_id.in_(store_ids))
            .group_by(Price.store_id)
        )
        cnt_result = await db.execute(count_stmt)
        for row in cnt_result.all():
            product_counts[row.store_id] = row.cnt

    response = [
        StoreNearby(
            id=n["store"].id,
            name=n["store"].name,
            slug=n["store"].slug,
            address=n["store"].address,
            city=n["store"].city,
            latitude=float(n["store"].latitude),
            longitude=float(n["store"].longitude),
            logo_url=n["store"].logo_url,
            distance_km=n["distance_km"],
            product_count=product_counts.get(n["store"].id, 0),
        )
        for n in nearby
    ]
    await cache.set(cache_key, [r.model_dump(mode="json") for r in response], ttl=TTL_STORES)
    return response


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/stores/{id}/products
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{store_id}/products", response_model=Paginated[StoreProductSummary],
            summary="Produits d'un magasin")
async def get_store_products(
    store_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, max_length=200),
    db: AsyncSession = Depends(get_db),
):
    cache_key = make_store_products_key(store_id, skip, limit)
    if search:
        cache_key += f":{search}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    store = await db.get(Store, store_id)
    if not store or not store.is_active:
        raise HTTPException(status_code=404, detail="Magasin introuvable")

    # Sous-requête : prix le plus récent par produit dans ce magasin
    subq = (
        select(
            Price.product_id,
            func.max(Price.recorded_at).label("latest"),
        )
        .where(Price.store_id == store_id)
        .group_by(Price.product_id)
        .subquery()
    )

    stmt = (
        select(Price, Product)
        .join(Product, Price.product_id == Product.id)
        .join(subq, and_(
            Price.product_id == subq.c.product_id,
            Price.recorded_at == subq.c.latest,
        ))
        .where(
            Price.store_id == store_id,
            Product.is_active == True,
        )
        .order_by(Product.name)
    )
    if search:
        stmt = stmt.where(Product.name.ilike(f"%{search}%"))

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    result = await db.execute(stmt.offset(skip).limit(limit))
    rows = result.all()

    summaries = [
        StoreProductSummary(
            product_id=product.id,
            product_name=product.name,
            product_image=product.image_url,
            price=float(price.price),
            is_promo=price.is_promo,
            promo_price=float(price.promo_price) if price.promo_price else None,
            effective_price=_effective_price(price),
            recorded_at=price.recorded_at,
        )
        for price, product in rows
    ]

    response = Paginated[StoreProductSummary](
        data=summaries,
        meta=PageMeta(total=total, skip=skip, limit=limit, has_more=(skip + limit) < total),
    )
    await cache.set(cache_key, response.model_dump(mode="json"), ttl=TTL_PRICES)
    return response


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/stores/route-optimize
# Algorithme : greedy nearest-neighbor (approximation TSP)
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/route-optimize", response_model=RouteOptimizeResponse,
            summary="Optimisation de parcours multi-magasins")
async def route_optimize(
    store_ids: str = Query(..., description="IDs de magasins séparés par virgule", example="1,2,3"),
    product_ids: str | None = Query(None, description="IDs de produits à acheter (optionnel)"),
    origin_lat: float | None = Query(None, description="Latitude de départ"),
    origin_lng: float | None = Query(None, description="Longitude de départ"),
    db: AsyncSession = Depends(get_db),
):
    # Validation IDs magasins
    try:
        sid_list = [int(x.strip()) for x in store_ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="Format store_ids invalide")
    if len(sid_list) < 2:
        raise HTTPException(status_code=422, detail="Au moins 2 magasins requis")
    if len(sid_list) > 20:
        raise HTTPException(status_code=422, detail="Maximum 20 magasins")

    # Validation IDs produits (optionnel)
    pid_list: list[int] = []
    if product_ids:
        try:
            pid_list = [int(x.strip()) for x in product_ids.split(",") if x.strip()]
        except ValueError:
            raise HTTPException(status_code=422, detail="Format product_ids invalide")

    # Récupère les magasins
    result = await db.execute(select(Store).where(Store.id.in_(sid_list), Store.is_active == True))
    stores = {s.id: s for s in result.scalars().all()}

    missing = [sid for sid in sid_list if sid not in stores]
    if missing:
        raise HTTPException(status_code=404, detail=f"Magasins introuvables : {missing}")

    # Pour chaque magasin, calcule les économies sur les produits demandés
    store_savings: dict[int, float] = {sid: 0.0 for sid in sid_list}
    store_products: dict[int, list[str]] = {sid: [] for sid in sid_list}

    if pid_list:
        for pid in pid_list:
            # Prix par magasin pour ce produit
            subq = (
                select(Price.store_id, func.max(Price.recorded_at).label("latest"))
                .where(Price.product_id == pid, Price.store_id.in_(sid_list))
                .group_by(Price.store_id)
                .subquery()
            )
            price_stmt = (
                select(Price, Product)
                .join(Product, Price.product_id == Product.id)
                .join(subq, and_(
                    Price.store_id == subq.c.store_id,
                    Price.recorded_at == subq.c.latest,
                ))
                .where(Price.product_id == pid)
            )
            price_result = await db.execute(price_stmt)
            price_rows = price_result.all()

            if not price_rows:
                continue

            price_map = {price.store_id: (_effective_price(price), product) for price, product in price_rows}
            all_prices = [v[0] for v in price_map.values()]
            max_price = max(all_prices)
            min_sid = min(price_map, key=lambda s: price_map[s][0])
            min_price, prod = price_map[min_sid]

            store_savings[min_sid] += round(max_price - min_price, 2)
            store_products[min_sid].append(prod.name)

    # Greedy nearest-neighbor TSP
    remaining = list(sid_list)
    ordered: list[int] = []
    total_distance = 0.0

    # Point de départ : origine fournie ou premier magasin de la liste
    if origin_lat is not None and origin_lng is not None:
        cur_lat, cur_lng = origin_lat, origin_lng
    else:
        first = stores[remaining[0]]
        cur_lat = float(first.latitude) if first.latitude else 0.0
        cur_lng = float(first.longitude) if first.longitude else 0.0

    while remaining:
        best_sid = None
        best_dist = float("inf")
        for sid in remaining:
            s = stores[sid]
            if s.latitude and s.longitude:
                d = _haversine_km(cur_lat, cur_lng, float(s.latitude), float(s.longitude))
            else:
                d = float("inf")
            if d < best_dist:
                best_dist = d
                best_sid = sid

        if best_sid is None:
            best_sid = remaining[0]
            best_dist = 0.0

        ordered.append(best_sid)
        remaining.remove(best_sid)
        if best_dist != float("inf"):
            total_distance += best_dist
        s = stores[best_sid]
        if s.latitude and s.longitude:
            cur_lat, cur_lng = float(s.latitude), float(s.longitude)

    stops: list[RouteStop] = []
    for order, sid in enumerate(ordered, start=1):
        store = stores[sid]
        stops.append(RouteStop(
            order=order,
            store_id=store.id,
            store_name=store.name,
            store_address=store.address,
            latitude=float(store.latitude) if store.latitude else None,
            longitude=float(store.longitude) if store.longitude else None,
            products_to_buy=store_products[sid],
            estimated_savings=round(store_savings[sid], 2),
        ))

    total_savings = round(sum(store_savings.values()), 2)

    return RouteOptimizeResponse(
        stops=stops,
        total_stores=len(stops),
        total_distance_km=round(total_distance, 2) if total_distance > 0 else None,
        total_savings=total_savings,
        algorithm="nearest-neighbor",
    )
