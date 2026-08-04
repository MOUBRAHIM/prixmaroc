from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func

from app.db import get_db
from app.models import User
from app.schemas import UserRead, UserUpdate
from app.utils.deps import get_current_user

router = APIRouter(prefix="/utilisateurs", tags=["utilisateurs"])


@router.get("/me", response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.put("/me", response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from app.utils.security import hash_password
    for field, value in payload.model_dump(exclude_none=True).items():
        if field == "password":
            setattr(current_user, "password_hash", hash_password(value))
        else:
            setattr(current_user, field, value)
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.delete("/me", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    await db.delete(current_user)
    await db.commit()


@router.get("/me/stats")
async def get_my_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Statistiques personnelles : nb scans, nb listes, économies estimées."""
    from app.models import OcrScan, ShoppingList
    from sqlalchemy import func as f

    scans_result = await db.execute(
        select(f.count(OcrScan.id)).where(OcrScan.user_id == current_user.id)
    )
    nb_scans = scans_result.scalar_one_or_none() or 0

    listes_result = await db.execute(
        select(f.count(ShoppingList.id)).where(ShoppingList.user_id == current_user.id)
    )
    nb_listes = listes_result.scalar_one_or_none() or 0

    # Économies estimées : 15 MAD par scan en moyenne (estimation)
    economies = round(nb_scans * 15.0, 2)

    return {
        "scans": nb_scans,
        "listes": nb_listes,
        "economies": economies,
    }


@router.post("/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Upload photo de profil (stockage local temporaire — remplacer par R2 en production)."""
    import uuid, os
    from pathlib import Path

    # Valide le type
    if file.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Format non supporté. Utilisez JPEG, PNG ou WebP.")

    # Sauvegarde locale (en prod, uploader vers Cloudflare R2)
    upload_dir = Path("uploads/avatars")
    upload_dir.mkdir(parents=True, exist_ok=True)
    ext = file.filename.rsplit(".", 1)[-1] if file.filename else "jpg"
    filename = f"{current_user.id}_{uuid.uuid4().hex[:8]}.{ext}"
    file_path = upload_dir / filename

    contents = await file.read()
    with open(file_path, "wb") as f_out:
        f_out.write(contents)

    avatar_url = f"/uploads/avatars/{filename}"
    current_user.avatar_url = avatar_url
    db.add(current_user)
    await db.commit()

    return {"avatar_url": avatar_url}
