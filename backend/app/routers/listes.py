import secrets
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.db import get_db
from app.models import ShoppingList, ShoppingListItem, User
from app.schemas import (
    ShoppingListCreate, ShoppingListUpdate, ShoppingListRead,
    ShoppingListItemCreate, ShoppingListItemUpdate, ShoppingListItemRead,
)
from app.utils.deps import get_current_user

router = APIRouter(prefix="/listes", tags=["listes"])


@router.get("", response_model=list[ShoppingListRead])
async def list_shopping_lists(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ShoppingList)
        .where(ShoppingList.user_id == current_user.id)
        .options(selectinload(ShoppingList.items))
        .order_by(ShoppingList.updated_at.desc())
    )
    return result.scalars().all()


@router.get("/{list_id}", response_model=ShoppingListRead)
async def get_shopping_list(
    list_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ShoppingList)
        .where(ShoppingList.id == list_id)
        .options(selectinload(ShoppingList.items))
    )
    lst = result.scalar_one_or_none()
    if not lst or lst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    return lst


@router.get("/shared/{token}", response_model=ShoppingListRead)
async def get_shared_list(token: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ShoppingList).where(ShoppingList.share_token == token, ShoppingList.is_shared == True)
    )
    lst = result.scalar_one_or_none()
    if not lst:
        raise HTTPException(status_code=404, detail="Liste partagée introuvable")
    return lst


@router.post("", response_model=ShoppingListRead, status_code=status.HTTP_201_CREATED)
async def create_shopping_list(
    payload: ShoppingListCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lst = ShoppingList(**payload.model_dump(), user_id=current_user.id)
    if payload.is_shared:
        lst.share_token = secrets.token_urlsafe(32)
    db.add(lst)
    await db.commit()
    result = await db.execute(
        select(ShoppingList).where(ShoppingList.id == lst.id).options(selectinload(ShoppingList.items))
    )
    return result.scalar_one()


@router.put("/{list_id}", response_model=ShoppingListRead)
async def update_shopping_list(
    list_id: int,
    payload: ShoppingListUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lst = await db.get(ShoppingList, list_id)
    if not lst or lst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(lst, field, value)
    if payload.is_shared and not lst.share_token:
        lst.share_token = secrets.token_urlsafe(32)
    await db.commit()
    result = await db.execute(
        select(ShoppingList).where(ShoppingList.id == lst.id).options(selectinload(ShoppingList.items))
    )
    return result.scalar_one()


@router.delete("/{list_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_shopping_list(
    list_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lst = await db.get(ShoppingList, list_id)
    if not lst or lst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    await db.delete(lst)
    await db.commit()


# ── Items ──────────────────────────────────────────────────────────────────────

@router.post("/{list_id}/items", response_model=ShoppingListItemRead, status_code=status.HTTP_201_CREATED)
async def add_item(
    list_id: int,
    payload: ShoppingListItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lst = await db.get(ShoppingList, list_id)
    if not lst or lst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    item = ShoppingListItem(**payload.model_dump(), list_id=list_id)
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.patch("/{list_id}/items/{item_id}", response_model=ShoppingListItemRead)
async def toggle_item(
    list_id: int,
    item_id: int,
    payload: ShoppingListItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lst = await db.get(ShoppingList, list_id)
    if not lst or lst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    item = await db.get(ShoppingListItem, item_id)
    if not item or item.list_id != list_id:
        raise HTTPException(status_code=404, detail="Article introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.put("/{list_id}/items/{item_id}", response_model=ShoppingListItemRead)
async def update_item(
    list_id: int,
    item_id: int,
    payload: ShoppingListItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lst = await db.get(ShoppingList, list_id)
    if not lst or lst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    item = await db.get(ShoppingListItem, item_id)
    if not item or item.list_id != list_id:
        raise HTTPException(status_code=404, detail="Article introuvable")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    await db.commit()
    await db.refresh(item)
    return item


@router.delete("/{list_id}/items/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    list_id: int,
    item_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lst = await db.get(ShoppingList, list_id)
    if not lst or lst.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Liste introuvable")
    item = await db.get(ShoppingListItem, item_id)
    if not item or item.list_id != list_id:
        raise HTTPException(status_code=404, detail="Article introuvable")
    await db.delete(item)
    await db.commit()
