from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from app.db import get_db
from app.models import Price, Product, Store, PriceAlert, User
from app.schemas import PriceCreate, PriceUpdate, PriceRead, PriceComparison, PriceAlertCreate, PriceAlertRead
from app.utils.deps import get_current_user

router = APIRouter(prefix="/prix", tags=["prix"])


# ── Alertes prix (doit être avant /{price_id}) ────────────────────────────────

@router.get("/alertes", response_model=list[PriceAlertRead])
async def list_alerts(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne toutes les alertes prix de l'utilisateur connecté."""
    stmt = select(PriceAlert).where(PriceAlert.user_id == current_user.id).order_by(PriceAlert.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/alertes", response_model=PriceAlertRead, status_code=status.HTTP_201_CREATED)
async def create_alert(
    payload: PriceAlertCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Crée une nouvelle alerte prix."""
    product = await db.get(Product, payload.product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    alert = PriceAlert(user_id=current_user.id, **payload.model_dump())
    db.add(alert)
    await db.commit()
    await db.refresh(alert)
    return alert


@router.delete("/alertes/{alert_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_alert(
    alert_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Supprime une alerte prix."""
    alert = await db.get(PriceAlert, alert_id)
    if not alert or alert.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Alerte introuvable")
    await db.delete(alert)
    await db.commit()


@router.get("/comparer/{product_id}", response_model=PriceComparison)
async def compare_prices(product_id: int, city: str | None = None, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    # Subquery: latest price ID per store (avoid duplicate store entries)
    latest_sub = (
        select(func.max(Price.id).label("max_id"))
        .where(Price.product_id == product_id)
        .group_by(Price.store_id)
        .subquery()
    )
    stmt = (
        select(Price, Store)
        .join(Store, Price.store_id == Store.id)
        .where(Price.id.in_(select(latest_sub.c.max_id)))
    )
    if city:
        stmt = stmt.where(Store.city.ilike(f"%{city}%"))

    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        raise HTTPException(status_code=404, detail="Aucun prix trouvé pour ce produit")

    prices_list = [
        {
            "store_id": store.id,
            "store_name": store.name,
            "store_city": store.city,
            "store_address": store.address,
            "store_lat": float(store.latitude) if store.latitude else None,
            "store_lng": float(store.longitude) if store.longitude else None,
            "price": float(price.price),
            "currency": price.currency,
            "is_promo": price.is_promo,
            "promo_price": float(price.promo_price) if price.promo_price else None,
            "source": price.source.value if hasattr(price.source, 'value') else str(price.source),
            "recorded_at": price.recorded_at,
        }
        for price, store in rows
    ]

    prices_values = [p["promo_price"] or p["price"] for p in prices_list]

    return PriceComparison(
        product_id=product_id,
        product_name=product.name,
        prices=prices_list,
        lowest_price=min(prices_values),
        highest_price=max(prices_values),
        average_price=sum(prices_values) / len(prices_values),
    )


@router.get("/{price_id}", response_model=PriceRead)
async def get_price(price_id: int, db: AsyncSession = Depends(get_db)):
    price = await db.get(Price, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Prix introuvable")
    return price


@router.post("/", response_model=PriceRead, status_code=status.HTTP_201_CREATED)
async def create_price(
    payload: PriceCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    price = Price(**payload.model_dump())
    db.add(price)
    await db.commit()
    await db.refresh(price)
    return price


@router.put("/{price_id}", response_model=PriceRead)
async def update_price(
    price_id: int,
    payload: PriceUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    price = await db.get(Price, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Prix introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(price, field, value)
    await db.commit()
    await db.refresh(price)
    return price


@router.delete("/{price_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_price(
    price_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    price = await db.get(Price, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Prix introuvable")
    await db.delete(price)
    await db.commit()
