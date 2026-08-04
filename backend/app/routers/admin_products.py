"""
Panel admin — Gestion des produits.

Endpoints :
  GET    /admin/products/openfoodfacts?q=   Recherche Open Food Facts (proxy)
  GET    /admin/products/without-photos     Produits sans image (pour upload)
  POST   /admin/products/import-csv          Import CSV en masse
  PATCH  /admin/products/{id}               Mise à jour partielle (photo + nutrition)
  POST   /admin/products/{id}/photo         Upload direct d'une photo (multipart)
"""
from __future__ import annotations

import csv
import io
import logging
import os
import uuid
from typing import Any

import httpx
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Product, Category
from app.utils.deps import get_superuser

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/admin/products", tags=["admin — products"])


# ── Schémas ────────────────────────────────────────────────────────────────────

class ProductPatch(BaseModel):
    name: str | None = None
    brand: str | None = None
    barcode: str | None = None
    image_url: str | None = None
    unit_size: str | None = None
    nutriscore: str | None = None
    calories: float | None = None
    proteins: float | None = None
    lipids: float | None = None
    carbs: float | None = None
    fibers: float | None = None
    category_id: int | None = None


class CsvImportResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    errors: list[str]


# ── Produits sans photo ────────────────────────────────────────────────────────

@router.get("/without-photos", summary="Produits sans image_url (à compléter)")
async def products_without_photos(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    """Retourne les produits actifs dont image_url est NULL ou vide."""
    stmt = (
        select(Product)
        .where(
            Product.is_active == True,
            (Product.image_url == None) | (Product.image_url == ""),
        )
        .order_by(Product.name)
    )
    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    result = await db.execute(stmt.offset(skip).limit(limit))
    products = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "products": [
            {
                "id": p.id,
                "name": p.name,
                "brand": p.brand,
                "barcode": p.barcode,
                "category_id": p.category_id,
            }
            for p in products
        ],
    }


# ── Open Food Facts autocomplete ───────────────────────────────────────────────

@router.get("/openfoodfacts", summary="Recherche Open Food Facts (proxy)")
async def search_open_food_facts(
    q: str = Query(..., min_length=2, description="Terme de recherche"),
    limit: int = Query(default=8, le=20),
    _=Depends(get_superuser),
) -> list[dict[str, Any]]:
    """
    Proxy vers l'API Open Food Facts pour trouver des produits à importer.
    Retourne les champs utiles pour remplir automatiquement le formulaire admin.
    """
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "search_terms": q,
        "search_simple": 1,
        "action": "process",
        "json": 1,
        "countries_tags": "morocco",
        "page_size": limit,
        "fields": "code,product_name,product_name_fr,brands,nutriscore_grade,"
                  "nutriments,image_front_small_url,categories_tags",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Open Food Facts inaccessible : {exc}",
        )

    products = []
    for p in data.get("products", []):
        nutriments = p.get("nutriments", {})
        name = (p.get("product_name_fr") or p.get("product_name") or "").strip()
        if not name:
            continue
        products.append({
            "barcode": p.get("code"),
            "name": name,
            "brand": (p.get("brands") or "").split(",")[0].strip() or None,
            "nutriscore": (p.get("nutriscore_grade") or "").upper() or None,
            "image_url": p.get("image_front_small_url"),
            "calories": nutriments.get("energy-kcal_100g"),
            "proteins": nutriments.get("proteins_100g"),
            "lipids": nutriments.get("fat_100g"),
            "carbs": nutriments.get("carbohydrates_100g"),
            "fibers": nutriments.get("fiber_100g"),
        })

    return products


# ── Mise à jour partielle d'un produit ────────────────────────────────────────

@router.patch("/{product_id}", summary="Mise à jour partielle (photo, nutrition, etc.)")
async def patch_product(
    product_id: int,
    payload: ProductPatch,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(product, field, value)

    await db.commit()
    await db.refresh(product)

    return {
        "id": product.id,
        "name": product.name,
        "brand": product.brand,
        "image_url": product.image_url,
        "nutriscore": product.nutriscore,
        "calories": product.calories,
        "proteins": product.proteins,
        "lipids": product.lipids,
        "carbs": product.carbs,
        "fibers": product.fibers,
    }


# ── Upload photo directe ───────────────────────────────────────────────────────

PHOTO_ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp"}
PHOTO_MAX_MB = 5


@router.post("/{product_id}/photo", summary="Upload direct d'une photo produit")
async def upload_product_photo(
    product_id: int,
    file: UploadFile = File(..., description="Photo du produit (JPEG, PNG, WebP, max 5 Mo)"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    """
    Upload une photo produit directement en multipart/form-data.

    - Si Cloudflare R2 est configuré (R2_BUCKET_NAME env) → stocké sur R2
    - Sinon → stocké localement dans /tmp/prixmaroc_photos/ (dev uniquement)
    - Met à jour `image_url` du produit en base
    """
    result = await db.execute(select(Product).where(Product.id == product_id))
    product = result.scalar_one_or_none()
    if not product:
        raise HTTPException(status_code=404, detail="Produit introuvable")

    if file.content_type not in PHOTO_ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Format non supporté. Acceptés : {', '.join(PHOTO_ALLOWED_MIME)}",
        )

    data = await file.read()
    if len(data) > PHOTO_MAX_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"Fichier trop volumineux (max {PHOTO_MAX_MB} Mo)")

    ext = {"image/jpeg": "jpg", "image/png": "png", "image/webp": "webp"}.get(file.content_type, "jpg")
    filename = f"products/{product_id}_{uuid.uuid4().hex[:8]}.{ext}"

    # ── Tentative upload R2 ───────────────────────────────────────────────────
    image_url: str | None = None
    bucket = os.getenv("R2_BUCKET_NAME")
    r2_endpoint = os.getenv("R2_ENDPOINT_URL")
    r2_access = os.getenv("R2_ACCESS_KEY_ID")
    r2_secret = os.getenv("R2_SECRET_ACCESS_KEY")
    r2_public = os.getenv("R2_PUBLIC_URL", "")

    if all([bucket, r2_endpoint, r2_access, r2_secret]):
        try:
            import boto3
            from botocore.config import Config as BotoConfig
            s3 = boto3.client(
                "s3",
                endpoint_url=r2_endpoint,
                aws_access_key_id=r2_access,
                aws_secret_access_key=r2_secret,
                config=BotoConfig(signature_version="s3v4"),
            )
            s3.put_object(
                Bucket=bucket,
                Key=filename,
                Body=data,
                ContentType=file.content_type,
                CacheControl="public, max-age=31536000",
            )
            image_url = f"{r2_public.rstrip('/')}/{filename}"
            logger.info(f"[Photo] Uploadé sur R2 : {image_url}")
        except Exception as exc:
            logger.warning(f"[Photo] R2 upload échoué, fallback local : {exc}")

    # ── Fallback local (développement) ───────────────────────────────────────
    if not image_url:
        local_dir = "/tmp/prixmaroc_photos/products"
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, os.path.basename(filename))
        with open(local_path, "wb") as f:
            f.write(data)
        image_url = f"/static/photos/{os.path.basename(filename)}"
        logger.info(f"[Photo] Sauvegardé localement : {local_path}")

    # ── Mise à jour BDD ───────────────────────────────────────────────────────
    product.image_url = image_url
    await db.commit()

    return {"product_id": product_id, "image_url": image_url, "size_bytes": len(data)}


# ── Import CSV en masse ────────────────────────────────────────────────────────

# Colonnes CSV attendues (insensibles à la casse)
CSV_FIELDS = {
    "name", "brand", "barcode", "category", "unit_size",
    "image_url", "nutriscore", "calories", "proteins",
    "lipids", "carbs", "fibers",
}

FLOAT_FIELDS = {"calories", "proteins", "lipids", "carbs", "fibers"}


def _slugify(text: str) -> str:
    import re, unicodedata
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")


@router.post(
    "/import-csv",
    response_model=CsvImportResult,
    status_code=status.HTTP_200_OK,
    summary="Import CSV produits en masse",
)
async def import_products_csv(
    file: UploadFile = File(..., description="Fichier CSV (UTF-8, séparateur virgule)"),
    update_existing: bool = Query(default=True, description="Mettre à jour si barcode existe déjà"),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
) -> CsvImportResult:
    """
    Importe des produits depuis un CSV.

    Colonnes acceptées (toutes optionnelles sauf `name`) :
    `name, brand, barcode, category, unit_size, image_url, nutriscore,
    calories, proteins, lipids, carbs, fibers`

    - Doublons détectés par `barcode` (EAN)
    - Si `update_existing=true`, les champs sont mis à jour
    - `category` = nom de la catégorie (crée si inexistante)
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Fichier CSV requis (.csv)")

    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")  # gère BOM UTF-8
    except UnicodeDecodeError:
        content = raw.decode("latin-1")

    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV vide ou sans en-tête")

    # Normalise les noms de colonnes
    fieldnames_lower = {f.strip().lower(): f for f in reader.fieldnames}

    inserted = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    # Cache catégories pour éviter les requêtes répétées
    category_cache: dict[str, int | None] = {}

    async def _get_or_create_category(name: str) -> int | None:
        key = name.lower().strip()
        if key in category_cache:
            return category_cache[key]
        r = await db.execute(select(Category).where(Category.name.ilike(name)))
        cat = r.scalar_one_or_none()
        if not cat:
            cat = Category(name=name.strip(), slug=_slugify(name))
            db.add(cat)
            await db.flush()
        category_cache[key] = cat.id
        return cat.id

    def _get(row: dict, col: str) -> str | None:
        original_key = fieldnames_lower.get(col)
        if not original_key:
            return None
        val = (row.get(original_key) or "").strip()
        return val if val else None

    rows = list(reader)
    for line_num, row in enumerate(rows, start=2):
        try:
            name = _get(row, "name")
            if not name:
                skipped += 1
                continue

            barcode = _get(row, "barcode")

            # Cherche un doublon par barcode
            existing: Product | None = None
            if barcode:
                r = await db.execute(select(Product).where(Product.barcode == barcode))
                existing = r.scalar_one_or_none()

            if existing and not update_existing:
                skipped += 1
                continue

            # Catégorie
            cat_name = _get(row, "category")
            category_id: int | None = None
            if cat_name:
                category_id = await _get_or_create_category(cat_name)

            # Champs numériques
            def _float(col: str) -> float | None:
                v = _get(row, col)
                if v is None:
                    return None
                try:
                    return float(v.replace(",", "."))
                except ValueError:
                    return None

            if existing:
                # Mise à jour
                existing.name = name
                if _get(row, "brand"):
                    existing.brand = _get(row, "brand")
                if _get(row, "image_url"):
                    existing.image_url = _get(row, "image_url")
                if _get(row, "unit_size"):
                    existing.unit_size = _get(row, "unit_size")
                if _get(row, "nutriscore"):
                    existing.nutriscore = (_get(row, "nutriscore") or "").upper()[:1] or None
                for fld in FLOAT_FIELDS:
                    v = _float(fld)
                    if v is not None:
                        setattr(existing, fld, v)
                if category_id:
                    existing.category_id = category_id
                updated += 1
            else:
                # Création
                slug_base = _slugify(name)
                # Slug unique
                slug = slug_base
                count = 0
                while True:
                    r = await db.execute(select(Product).where(Product.slug == slug))
                    if not r.scalar_one_or_none():
                        break
                    count += 1
                    slug = f"{slug_base}-{count}"

                ns_raw = (_get(row, "nutriscore") or "").upper()
                product = Product(
                    name=name,
                    slug=slug,
                    brand=_get(row, "brand"),
                    barcode=barcode,
                    image_url=_get(row, "image_url"),
                    unit_size=_get(row, "unit_size"),
                    nutriscore=ns_raw[:1] if ns_raw else None,
                    calories=_float("calories"),
                    proteins=_float("proteins"),
                    lipids=_float("lipids"),
                    carbs=_float("carbs"),
                    fibers=_float("fibers"),
                    category_id=category_id,
                )
                db.add(product)
                inserted += 1

        except Exception as exc:
            errors.append(f"Ligne {line_num}: {exc}")
            if len(errors) >= 20:
                errors.append("… (trop d'erreurs, import arrêté)")
                break

    try:
        await db.commit()
    except Exception as exc:
        await db.rollback()
        raise HTTPException(status_code=500, detail=f"Erreur lors de la sauvegarde : {exc}")

    logger.info(
        f"[CSV Import] Inséré: {inserted}, Mis à jour: {updated}, "
        f"Ignoré: {skipped}, Erreurs: {len(errors)}"
    )

    return CsvImportResult(
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=errors,
    )
