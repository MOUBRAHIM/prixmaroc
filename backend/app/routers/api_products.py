"""
Router /api/products

GET /api/products                    Recherche paginée (search, category, city)
GET /api/products/compare            Comparaison multi-produits
GET /api/products/{id}               Détail + prix par magasin
GET /api/products/{id}/price-history Historique 30/90 jours
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, or_, and_, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import Category, Price, Product, Store
from app.schemas.api import (
    CompareProduct,
    CompareResponse,
    PageMeta,
    Paginated,
    PriceHistory,
    PriceInStore,
    PricePoint,
    ProductDetail,
    ProductSummary,
)
from app.utils.cache import (
    TTL_PRICES,
    TTL_PRODUCTS,
    cache,
    make_history_key,
    make_prices_key,
    make_product_key,
    make_search_key,
)

router = APIRouter(prefix="/api/products", tags=["products"])


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _effective_price(price: Price) -> float:
    if price.is_promo and price.promo_price:
        return float(price.promo_price)
    return float(price.price)


async def _latest_price_per_store(
    product_id: int,
    city: str | None,
    db: AsyncSession,
) -> list[Price]:
    """Retourne le prix le plus récent de chaque magasin pour un produit."""
    # Sous-requête : max(recorded_at) par store
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
        select(Price)
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
    return result.scalars().all()


async def _build_product_detail(
    product: Product,
    prices: list[Price],
    db: AsyncSession,
) -> ProductDetail:
    """Construit un ProductDetail à partir d'un produit et de ses prix."""
    store_ids = [p.store_id for p in prices]
    stores_map: dict[int, Store] = {}
    if store_ids:
        res = await db.execute(select(Store).where(Store.id.in_(store_ids)))
        stores_map = {s.id: s for s in res.scalars().all()}

    cat_name = None
    if product.category_id:
        cat = await db.get(Category, product.category_id)
        cat_name = cat.name if cat else None

    price_entries: list[PriceInStore] = []
    for p in sorted(prices, key=_effective_price):
        store = stores_map.get(p.store_id)
        if not store:
            continue
        price_entries.append(PriceInStore(
            store_id=store.id,
            store_name=store.name,
            store_city=store.city,
            store_logo=store.logo_url,
            price=float(p.price),
            currency=p.currency,
            is_promo=p.is_promo,
            promo_price=float(p.promo_price) if p.promo_price else None,
            effective_price=_effective_price(p),
            source=p.source.value if hasattr(p.source, "value") else str(p.source) if p.source else None,
            recorded_at=p.recorded_at,
        ))

    effectives = [e.effective_price for e in price_entries]
    return ProductDetail(
        id=product.id,
        name=product.name,
        slug=product.slug,
        barcode=product.barcode,
        brand=product.brand,
        description=product.description,
        image_url=product.image_url,
        unit=product.unit,
        unit_size=product.unit_size,
        category_name=cat_name,
        prices=price_entries,
        lowest_price=min(effectives) if effectives else None,
        highest_price=max(effectives) if effectives else None,
        average_price=round(sum(effectives) / len(effectives), 2) if effectives else None,
        store_count=len(price_entries),
        # Infos nutritionnelles
        calories=getattr(product, "calories", None),
        proteins=getattr(product, "proteins", None),
        lipids=getattr(product, "lipids", None),
        carbs=getattr(product, "carbs", None),
        fibers=getattr(product, "fibers", None),
        nutriscore=getattr(product, "nutriscore", None),
    )


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/products
# ──────────────────────────────────────────────────────────────────────────────

@router.get("", response_model=Paginated[ProductSummary], summary="Recherche de produits")
async def search_products(
    q: str | None = Query(None, description="Nom, barcode ou marque (alias: search)", max_length=200),
    search: str | None = Query(None, description="Nom, barcode ou marque", max_length=200),
    category_id: int | None = Query(None, description="ID de catégorie (alias: category)"),
    category: int | None = Query(None, description="ID de catégorie"),
    city: str | None = Query(None, description="Filtrer par ville"),
    brand: str | None = Query(None, description="Filtrer par marque"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    # Aliases : q → search, category_id → category
    search = q or search
    category = category_id or category
    cache_key = make_search_key(search or "", category, city, skip, limit)
    cached = await cache.get(cache_key)
    if cached:
        return cached

    stmt = (
        select(Product)
        .where(Product.is_active == True)
        .order_by(Product.name)
    )

    if search:
        term = f"%{search}%"
        stmt = stmt.where(or_(
            Product.name.ilike(term),
            Product.barcode == search,
            Product.brand.ilike(term),
        ))
    if category:
        stmt = stmt.where(Product.category_id == category)
    if brand:
        stmt = stmt.where(Product.brand.ilike(f"%{brand}%"))

    # Filtrage par ville via jointure Prix → Magasin
    if city:
        stmt = stmt.where(
            Product.id.in_(
                select(Price.product_id)
                .join(Store, Price.store_id == Store.id)
                .where(Store.city.ilike(f"%{city}%"), Store.is_active == True)
                .distinct()
            )
        )

    # Comptage total
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    result = await db.execute(stmt.offset(skip).limit(limit))
    products = result.scalars().all()

    # Enrichissement : prix min/max + nombre de magasins (prix RÉCENT par magasin)
    summaries: list[ProductSummary] = []

    # Récupère les derniers prix de tous les produits en une seule requête groupée
    if products:
        product_ids_batch = [p.id for p in products]

        # Sous-requête : max(recorded_at) par (product_id, store_id)
        from sqlalchemy import tuple_
        subq_batch = (
            select(
                Price.product_id,
                Price.store_id,
                func.max(Price.recorded_at).label("latest"),
            )
            .where(Price.product_id.in_(product_ids_batch))
            .group_by(Price.product_id, Price.store_id)
            .subquery()
        )
        prices_batch_q = await db.execute(
            select(Price)
            .join(subq_batch, and_(
                Price.product_id == subq_batch.c.product_id,
                Price.store_id == subq_batch.c.store_id,
                Price.recorded_at == subq_batch.c.latest,
            ))
            .where(Price.product_id.in_(product_ids_batch))
        )
        all_prices = prices_batch_q.scalars().all()
        prices_by_product: dict[int, list[Price]] = {}
        for pr in all_prices:
            prices_by_product.setdefault(pr.product_id, []).append(pr)
    else:
        prices_by_product = {}

    # Cache catégories
    cat_cache: dict[int, str | None] = {}

    for p in products:
        plist = prices_by_product.get(p.id, [])
        effectives = [_effective_price(x) for x in plist]

        cat_name: str | None = None
        if p.category_id:
            if p.category_id not in cat_cache:
                cat = await db.get(Category, p.category_id)
                cat_cache[p.category_id] = cat.name if cat else None
            cat_name = cat_cache[p.category_id]

        # Nom affiché : inclut le grammage s'il est absent du nom
        display_name = p.name
        if p.unit_size and p.unit_size not in display_name:
            display_name = f"{p.name} {p.unit_size}"

        summaries.append(ProductSummary(
            id=p.id,
            name=display_name,
            slug=p.slug,
            brand=p.brand,
            image_url=p.image_url,
            unit_size=p.unit_size,
            category_name=cat_name,
            lowest_price=min(effectives) if effectives else None,
            highest_price=max(effectives) if effectives else None,
            store_count=len({x.store_id for x in plist}),
            has_promo=any(x.is_promo for x in plist),
        ))

    response = Paginated[ProductSummary](
        data=summaries,
        meta=PageMeta(total=total, skip=skip, limit=limit, has_more=(skip + limit) < total),
    )
    # TTL_PRICES (1h) au lieu de TTL_PRODUCTS (24h) pour refléter les mises à jour de prix
    await cache.set(cache_key, response.model_dump(mode="json"), ttl=TTL_PRICES)
    return response


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/products/compare
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/compare", response_model=CompareResponse, summary="Comparer plusieurs produits")
async def compare_products(
    ids: str = Query(..., description="IDs séparés par virgule, ex: 1,2,3", example="1,2,3"),
    city: str | None = Query(None, description="Filtrer par ville"),
    db: AsyncSession = Depends(get_db),
):
    # Validation des IDs
    try:
        product_ids = [int(x.strip()) for x in ids.split(",") if x.strip()]
    except ValueError:
        raise HTTPException(status_code=422, detail="Format d'IDs invalide (attendu: entiers séparés par virgule)")

    if len(product_ids) < 2:
        raise HTTPException(status_code=422, detail="Au moins 2 produits requis pour la comparaison")
    if len(product_ids) > 10:
        raise HTTPException(status_code=422, detail="Maximum 10 produits par comparaison")

    results: list[CompareProduct] = []
    store_sets: list[set[str]] = []

    for pid in product_ids:
        product = await db.get(Product, pid)
        if not product or not product.is_active:
            raise HTTPException(status_code=404, detail=f"Produit {pid} introuvable")

        prices = await _latest_price_per_store(pid, city, db)
        detail = await _build_product_detail(product, prices, db)

        cheapest_name = detail.prices[0].store_name if detail.prices else None
        savings = (
            round(detail.highest_price - detail.lowest_price, 2)
            if detail.highest_price and detail.lowest_price else None
        )

        results.append(CompareProduct(
            product=detail,
            cheapest_store=cheapest_name,
            savings_vs_max=savings,
        ))
        store_sets.append({p.store_name for p in detail.prices})

    common = list(store_sets[0].intersection(*store_sets[1:])) if store_sets else []

    return CompareResponse(products=results, common_stores=sorted(common))


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/products/{id}
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{product_id}", response_model=ProductDetail, summary="Détail d'un produit")
async def get_product(
    product_id: int,
    city: str | None = Query(None, description="Filtrer les prix par ville"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = make_prices_key(product_id, city)
    cached = await cache.get(cache_key)
    if cached:
        return cached

    product = await db.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    prices = await _latest_price_per_store(product_id, city, db)
    detail = await _build_product_detail(product, prices, db)

    await cache.set(cache_key, detail.model_dump(mode="json"), ttl=TTL_PRICES)
    return detail


# ──────────────────────────────────────────────────────────────────────────────
# GET /api/products/{id}/price-history
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/{product_id}/price-history", response_model=PriceHistory,
            summary="Historique des prix (30 ou 90 jours)")
async def get_price_history(
    product_id: int,
    days: int = Query(30, description="Période en jours", ge=7, le=365),
    store_id: int | None = Query(None, description="Filtrer par magasin"),
    db: AsyncSession = Depends(get_db),
):
    cache_key = make_history_key(product_id, days)
    if store_id:
        cache_key += f":{store_id}"
    cached = await cache.get(cache_key)
    if cached:
        return cached

    product = await db.get(Product, product_id)
    if not product or not product.is_active:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    since = datetime.now(timezone.utc) - timedelta(days=days)

    stmt = (
        select(Price, Store.name.label("store_name"))
        .join(Store, Price.store_id == Store.id)
        .where(
            Price.product_id == product_id,
            Price.recorded_at >= since,
            Store.is_active == True,
        )
        .order_by(Price.recorded_at)
    )
    if store_id:
        stmt = stmt.where(Price.store_id == store_id)

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail=f"Aucun historique de prix sur {days} jours pour ce produit",
        )

    points: list[PricePoint] = []
    for price, store_name in rows:
        points.append(PricePoint(
            date=price.recorded_at.strftime("%Y-%m-%d"),
            price=_effective_price(price),
            store_id=price.store_id,
            store_name=store_name,
            is_promo=price.is_promo,
        ))

    all_prices = [p.price for p in points]
    response = PriceHistory(
        product_id=product_id,
        product_name=product.name,
        days=days,
        points=points,
        min_price=min(all_prices) if all_prices else None,
        max_price=max(all_prices) if all_prices else None,
        avg_price=round(sum(all_prices) / len(all_prices), 2) if all_prices else None,
    )

    await cache.set(cache_key, response.model_dump(mode="json"), ttl=TTL_PRICES)
    return response
