from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.db import get_db
from app.models import Store
from app.schemas import StoreCreate, StoreUpdate, StoreRead
from app.utils.deps import get_current_user

router = APIRouter(prefix="/magasins", tags=["magasins"])


@router.get("/", response_model=list[StoreRead])
async def list_stores(
    city: str | None = None,
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Store).where(Store.is_active == True)
    if city:
        stmt = stmt.where(Store.city.ilike(f"%{city}%"))
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/nearby", response_model=list[StoreRead])
async def nearby_stores(
    lat: float = Query(...),
    lng: float = Query(...),
    radius_km: float = Query(default=5.0),
    db: AsyncSession = Depends(get_db),
):
    """Retourne les magasins dans un rayon donné (filtre approximatif par bounding box)."""
    # ~1 degré lat ≈ 111km
    delta = radius_km / 111.0
    stmt = select(Store).where(
        Store.latitude.between(lat - delta, lat + delta),
        Store.longitude.between(lng - delta, lng + delta),
        Store.is_active == True,
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{store_id}", response_model=StoreRead)
async def get_store(store_id: int, db: AsyncSession = Depends(get_db)):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Magasin introuvable")
    return store


@router.post("/", response_model=StoreRead, status_code=status.HTTP_201_CREATED)
async def create_store(
    payload: StoreCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    store = Store(**payload.model_dump())
    db.add(store)
    await db.commit()
    await db.refresh(store)
    return store


@router.put("/{store_id}", response_model=StoreRead)
async def update_store(
    store_id: int,
    payload: StoreUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Magasin introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(store, field, value)
    await db.commit()
    await db.refresh(store)
    return store


@router.delete("/{store_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_store(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Magasin introuvable")
    await db.delete(store)
    await db.commit()
