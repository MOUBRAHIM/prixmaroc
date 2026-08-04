"""
Router admin — Import CSV de prix et gestion des prix manuels.

Endpoints :
  POST /admin/prices/import-csv   Import de prix depuis CSV
  GET  /admin/prices              Liste des prix (filtrable)
  PATCH /admin/prices/{id}        Correction manuelle d'un prix
  DELETE /admin/prices/{id}       Suppression d'un prix erroné
"""
from __future__ import annotations

import csv
import io
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from typing import Any

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.price import Price, PriceSource
from app.models.product import Product
from app.models.store import Store
from app.utils.deps import get_db, get_superuser
from app.utils.cache import cache

router = APIRouter(prefix="/admin/prices", tags=["admin-prices"])


# ── Schémas ───────────────────────────────────────────────────────────────────

class CsvPriceResult(BaseModel):
    inserted: int
    updated: int
    skipped: int
    errors: list[str]


class PricePatch(BaseModel):
    price: float | None = None
    is_promo: bool | None = None
    promo_price: float | None = None


# ── Utilitaires ───────────────────────────────────────────────────────────────

def _normalize(text: str) -> str:
    """Normalise un texte pour la comparaison (minuscules, sans accents)."""
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    return text.lower().strip()


def _best_match(query: str, candidates: list[tuple[int, str]], threshold: float = 0.6) -> int | None:
    """Retourne l'id du meilleur candidat dont le score >= threshold, ou None."""
    q = _normalize(query)
    best_id = None
    best_score = 0.0
    for cand_id, cand_name in candidates:
        score = SequenceMatcher(None, q, _normalize(cand_name)).ratio()
        if score > best_score:
            best_score = score
            best_id = cand_id
    if best_score >= threshold:
        return best_id
    return None


# ── Import CSV ────────────────────────────────────────────────────────────────

@router.post(
    "/import-csv",
    response_model=CsvPriceResult,
    status_code=status.HTTP_200_OK,
    summary="Import CSV de prix en masse",
)
async def import_prices_csv(
    file: UploadFile = File(..., description="Fichier CSV (UTF-8, séparateur virgule ou point-virgule)"),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(get_superuser),
) -> CsvPriceResult:
    """
    Importe des prix depuis un fichier CSV.

    **Colonnes acceptées :**
    ```
    product_name*  store_name  city  price*  is_promo  barcode
    ```
    *(* = obligatoire)*

    - `product_name` : nom du produit (correspondance approx. avec le catalogue)
    - `store_name` : nom du magasin (ex: "Marjane Casablanca") — optionnel
    - `city` : si `store_name` ambigu, précise la ville pour choisir la bonne enseigne
    - `price` : prix en MAD (décimal, ex: 12.50 ou 12,50)
    - `is_promo` : 1 / true / oui → prix promotionnel (défaut: false)
    - `barcode` : code-barres EAN pour une correspondance exacte produit

    **Matching produit** : code-barres prioritaire, sinon similarité de texte ≥ 60%
    **Matching magasin** : ILIKE `%store_name%`, filtré par `city` si fourni
    """
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Fichier CSV requis (.csv)")

    raw = await file.read()
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        content = raw.decode("latin-1")

    # Détecte le séparateur (virgule ou point-virgule)
    first_line = content.split("\n")[0]
    sep = ";" if first_line.count(";") > first_line.count(",") else ","

    reader = csv.DictReader(io.StringIO(content), delimiter=sep)
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="CSV vide ou sans en-tête")

    # Normalise les noms de colonnes
    fmap = {f.strip().lower(): f for f in reader.fieldnames}

    def _get(row: dict, col: str) -> str | None:
        key = fmap.get(col)
        if not key:
            return None
        v = (row.get(key) or "").strip()
        return v if v else None

    # Charge tous les produits et magasins en mémoire pour matching rapide
    prod_res = await db.execute(
        select(Product.id, Product.name, Product.barcode)
        .where(Product.is_active == True)
    )
    all_products = prod_res.fetchall()   # [(id, name, barcode)]

    store_res = await db.execute(
        select(Store.id, Store.name, Store.city)
        .where(Store.is_active == True)
    )
    all_stores = store_res.fetchall()   # [(id, name, city)]

    # Index barcode → product_id
    barcode_index: dict[str, int] = {
        row[2]: row[0] for row in all_products if row[2]
    }

    now = datetime.now(timezone.utc)
    inserted = 0
    updated = 0
    skipped = 0
    errors: list[str] = []

    rows = list(reader)
    for line_num, row in enumerate(rows, start=2):
        product_name = _get(row, "product_name") or _get(row, "nom") or _get(row, "produit")
        if not product_name:
            skipped += 1
            errors.append(f"Ligne {line_num} : `product_name` manquant")
            continue

        price_str = _get(row, "price") or _get(row, "prix")
        if not price_str:
            skipped += 1
            errors.append(f"Ligne {line_num} : `price` manquant pour «{product_name}»")
            continue

        try:
            price_val = float(price_str.replace(",", "."))
            if price_val <= 0:
                raise ValueError
        except ValueError:
            skipped += 1
            errors.append(f"Ligne {line_num} : prix invalide «{price_str}» pour «{product_name}»")
            continue

        # ── Résolution produit ──────────────────────────────────────────────
        product_id: int | None = None
        barcode = _get(row, "barcode") or _get(row, "ean") or _get(row, "code_barre")
        if barcode and barcode in barcode_index:
            product_id = barcode_index[barcode]

        if not product_id:
            product_id = _best_match(
                product_name,
                [(r[0], r[1]) for r in all_products],
                threshold=0.60,
            )

        if not product_id:
            skipped += 1
            errors.append(f"Ligne {line_num} : produit introuvable «{product_name}»")
            continue

        # ── Résolution magasin (optionnel) ──────────────────────────────────
        store_id: int | None = None
        store_name = _get(row, "store_name") or _get(row, "magasin") or _get(row, "enseigne")
        city = _get(row, "city") or _get(row, "ville")

        if store_name:
            candidates = [
                (r[0], f"{r[1]} {r[2] or ''}".strip())
                for r in all_stores
                if city is None or (r[2] or "").lower() == city.lower()
            ]
            store_id = _best_match(store_name, candidates, threshold=0.55)
            if not store_id and city:
                # Fallback sans filtre ville
                candidates_all = [(r[0], r[1]) for r in all_stores]
                store_id = _best_match(store_name, candidates_all, threshold=0.55)

        if not store_id:
            # Utilise un magasin générique "Manuel" (id=1 si inexistant → on skip)
            default_store = await db.execute(
                select(Store).where(Store.name.ilike("%manuel%")).limit(1)
            )
            ds = default_store.scalar_one_or_none()
            if ds:
                store_id = ds.id
            else:
                skipped += 1
                errors.append(f"Ligne {line_num} : magasin introuvable «{store_name or 'non fourni'}» pour «{product_name}»")
                continue

        # ── is_promo ────────────────────────────────────────────────────────
        promo_raw = (_get(row, "is_promo") or _get(row, "promo") or "").lower()
        is_promo = promo_raw in ("1", "true", "oui", "yes", "promo", "o")

        # ── Cherche un prix existant (même produit + magasin) ─────────────
        existing_res = await db.execute(
            select(Price).where(
                Price.product_id == product_id,
                Price.store_id == store_id,
                Price.source == PriceSource.MANUAL,
            ).order_by(Price.recorded_at.desc()).limit(1)
        )
        existing = existing_res.scalar_one_or_none()

        if existing:
            existing.price = round(price_val, 2)
            existing.is_promo = is_promo
            existing.promo_price = round(price_val, 2) if is_promo else None
            existing.recorded_at = now
            updated += 1
        else:
            db.add(Price(
                product_id=product_id,
                store_id=store_id,
                price=round(price_val, 2),
                currency="MAD",
                is_promo=is_promo,
                promo_price=round(price_val, 2) if is_promo else None,
                source=PriceSource.MANUAL,
                recorded_at=now,
            ))
            inserted += 1

    await db.commit()

    # Invalide le cache des prix
    await cache.invalidate_prefix("prixmaroc:prices:")
    await cache.invalidate_prefix("prixmaroc:products:search:")

    return CsvPriceResult(
        inserted=inserted,
        updated=updated,
        skipped=skipped,
        errors=errors[:50],  # limite les erreurs retournées
    )


# ── GET /admin/prices ─────────────────────────────────────────────────────────

@router.get("", summary="Liste paginée des prix")
async def list_prices(
    product_id: int | None = Query(None),
    store_id: int | None = Query(None),
    source: str | None = Query(None, description="scraper | ocr | manual | ai"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(get_superuser),
):
    """Liste des prix avec filtre optionnel par produit, magasin et source."""
    stmt = (
        select(
            Price.id,
            Price.price,
            Price.is_promo,
            Price.source,
            Price.recorded_at,
            Product.name.label("product_name"),
            Store.name.label("store_name"),
            Store.city.label("store_city"),
        )
        .join(Product, Price.product_id == Product.id)
        .join(Store, Price.store_id == Store.id)
    )

    if product_id:
        stmt = stmt.where(Price.product_id == product_id)
    if store_id:
        stmt = stmt.where(Price.store_id == store_id)
    if source:
        stmt = stmt.where(Price.source == source)

    total_res = await db.execute(select(func.count()).select_from(stmt.subquery()))
    total = total_res.scalar_one()

    stmt = stmt.order_by(Price.recorded_at.desc()).offset((page - 1) * limit).limit(limit)
    result = await db.execute(stmt)
    rows = result.mappings().all()

    return {
        "total": total,
        "page": page,
        "limit": limit,
        "items": [dict(r) for r in rows],
    }


# ── PATCH /admin/prices/{id} ──────────────────────────────────────────────────

@router.patch("/{price_id}", summary="Correction manuelle d'un prix")
async def patch_price(
    price_id: int,
    payload: PricePatch = Body(...),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(get_superuser),
):
    """Modifie un prix existant (source devient 'manual')."""
    price = await db.get(Price, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Prix introuvable")

    if payload.price is not None:
        price.price = round(payload.price, 2)
    if payload.is_promo is not None:
        price.is_promo = payload.is_promo
    if payload.promo_price is not None:
        price.promo_price = round(payload.promo_price, 2)

    price.source = PriceSource.MANUAL
    price.recorded_at = datetime.now(timezone.utc)
    await db.commit()

    await cache.invalidate_prefix("prixmaroc:prices:")
    return {"status": "updated", "id": price_id}


# ── DELETE /admin/prices/{id} ─────────────────────────────────────────────────

@router.delete("/{price_id}", status_code=status.HTTP_200_OK, summary="Suppression d'un prix erroné")
async def delete_price(
    price_id: int,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(get_superuser),
):
    """Supprime un prix (irréversible)."""
    price = await db.get(Price, price_id)
    if not price:
        raise HTTPException(status_code=404, detail="Prix introuvable")
    await db.delete(price)
    await db.commit()
    await cache.invalidate_prefix("prixmaroc:prices:")
    return {"status": "deleted", "id": price_id}
