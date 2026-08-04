from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.db import get_db
from app.models import Product
from app.schemas import ProductCreate, ProductUpdate, ProductRead
from app.utils.deps import get_current_user

router = APIRouter(prefix="/produits", tags=["produits"])


@router.get("/", response_model=list[ProductRead])
async def list_products(
    q: str | None = Query(None, description="Recherche par nom ou barcode"),
    category_id: int | None = None,
    brand: str | None = None,
    skip: int = 0,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
):
    stmt = select(Product).where(Product.is_active == True)
    if q:
        stmt = stmt.where(
            or_(Product.name.ilike(f"%{q}%"), Product.barcode == q)
        )
    if category_id:
        stmt = stmt.where(Product.category_id == category_id)
    if brand:
        stmt = stmt.where(Product.brand.ilike(f"%{brand}%"))
    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{product_id}", response_model=ProductRead)
async def get_product(product_id: int, db: AsyncSession = Depends(get_db)):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return product


@router.get("/barcode/{barcode}", response_model=ProductRead)
async def get_by_barcode(barcode: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Product).where(Product.barcode == barcode))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    return product


@router.post("/", response_model=ProductRead, status_code=status.HTTP_201_CREATED)
async def create_product(
    payload: ProductCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    product = Product(**payload.model_dump())
    db.add(product)
    await db.commit()
    await db.refresh(product)
    return product


@router.put("/{product_id}", response_model=ProductRead)
async def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(product, field, value)
    await db.commit()
    await db.refresh(product)
    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_product(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_current_user),
):
    product = await db.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")
    await db.delete(product)
    await db.commit()
