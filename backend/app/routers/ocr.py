"""Router OCR — upload et analyse de tickets de caisse."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import OcrScan, User
from app.models.price import Price, PriceSource
from app.models.product import Product
from app.models.store import Store
from app.models.ocr_scan import ScanStatus
from app.schemas import OcrScanRead
from app.services.ocr_service import OcrService
from app.utils.deps import get_current_user, get_optional_user
from app.utils.cache import cache

router = APIRouter(prefix="/ocr", tags=["ocr"])


class CorrectedItem(BaseModel):
    """Article dont l'utilisateur a corrigé le nom et/ou le prix."""
    name: str
    quantity: float = 1.0
    unit_price: float
    total_price: float
    is_promo: bool = False


class ConfirmPayload(BaseModel):
    store_id: Optional[int] = None          # override manuel si le nom détecté est ambigu
    corrections: Optional[list[CorrectedItem]] = None  # items corrigés par l'utilisateur

ALLOWED_MIME = {"image/jpeg", "image/png", "image/webp", "application/pdf"}
MAX_SIZE_MB = 10


@router.post("/scan", response_model=OcrScanRead, status_code=status.HTTP_201_CREATED)
async def scan_receipt(
    file: UploadFile = File(..., description="Ticket de caisse (JPEG, PNG, PDF)"),
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_user),
) -> OcrScanRead:
    """
    Analyse un ticket de caisse et retourne les produits + prix détectés.

    - Accepte : JPEG, PNG, WebP, PDF
    - Limite : 10 Mo
    - Langue OCR : français + arabe (ara+fra)
    - Fonctionne en mode invité (scan non sauvegardé en historique)
    """
    # ── Validation ────────────────────────────────────────────────────────────
    if file.content_type not in ALLOWED_MIME:
        raise HTTPException(
            status_code=415,
            detail=f"Format non supporté. Acceptés : {', '.join(ALLOWED_MIME)}",
        )

    image_data = await file.read()
    if len(image_data) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=413,
            detail=f"Fichier trop volumineux (max {MAX_SIZE_MB} Mo)",
        )

    # ── Enregistrement en BDD (uniquement si connecté) ────────────────────────
    scan = OcrScan(
        user_id=current_user.id if current_user else None,
        image_url=file.filename or "upload",
        status=ScanStatus.PROCESSING,
    )
    db.add(scan)
    await db.commit()
    await db.refresh(scan)

    # ── Pipeline OCR ─────────────────────────────────────────────────────────
    try:
        # Load product catalog from DB for better fuzzy matching
        catalog_result = await db.execute(select(Product.name).limit(500))
        catalog = [row[0] for row in catalog_result.fetchall() if row[0]]

        service = OcrService(catalog=catalog or None)
        result = service.process_image(image_data, file.content_type)

        scan.raw_text = result["raw_text"]
        scan.parsed_data = result
        scan.status = ScanStatus.DONE
        scan.processed_at = datetime.now(timezone.utc)

    except Exception as exc:
        scan.status = ScanStatus.FAILED
        scan.error_message = str(exc)
        await db.commit()
        raise HTTPException(status_code=500, detail=f"Erreur OCR : {exc}") from exc

    await db.commit()
    await db.refresh(scan)

    return OcrScanRead.model_validate(scan)


@router.post(
    "/confirm/{scan_id}",
    summary="Confirme un scan et enregistre les prix en base de données",
)
async def confirm_scan(
    scan_id: int,
    payload: ConfirmPayload = Body(default_factory=ConfirmPayload),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Valide les résultats OCR d'un ticket et :
    1. Sauvegarde les prix détectés en table `prices` (source=OCR) pour le magasin
    2. Permet de corriger les erreurs de prix scraping en temps réel
    3. Alimente l'historique d'achats de l'utilisateur

    - Si `store_id` est fourni : utilisé directement
    - Sinon : déduit du nom de magasin détecté par OCR (matching approximatif)
    """
    # ── Récupère le scan ──────────────────────────────────────────────────────
    scan = await db.get(OcrScan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan introuvable")
    if scan.status != ScanStatus.DONE:
        raise HTTPException(status_code=422, detail="Le scan n'est pas encore terminé")

    parsed = scan.parsed_data or {}

    # Vérification si déjà confirmé
    if parsed.get("confirmed"):
        return {
            "status": "already_confirmed",
            "store_id": parsed.get("store_id"),
            "prices_saved": parsed.get("prices_saved", 0),
        }

    # ── Résolution du magasin ────────────────────────────────────────────────
    resolved_store_id: int | None = payload.store_id

    if not resolved_store_id:
        store_info = parsed.get("store", {}) or {}
        store_name = (store_info.get("name") or store_info.get("chain") or "").strip()
        if store_name:
            # Matching insensible à la casse — prend le premier résultat
            res = await db.execute(
                select(Store)
                .where(Store.name.ilike(f"%{store_name}%"), Store.is_active == True)
                .limit(1)
            )
            found = res.scalar_one_or_none()
            if found:
                resolved_store_id = found.id

    # ── Utilise les corrections de l'utilisateur si fournies ─────────────────
    # (sinon, utilise les items du scan OCR brut)
    if payload.corrections:
        items = [c.model_dump() for c in payload.corrections]
        # Sauvegarde les corrections dans parsed_data pour audit / ML
        scan.parsed_data = {
            **parsed,
            "items_corrected": items,
            "has_user_corrections": True,
        }
        parsed = scan.parsed_data
    else:
        items = parsed.get("items", []) or []

    # ── Enregistrement des prix ───────────────────────────────────────────────
    saved_prices = 0
    now = datetime.now(timezone.utc)

    if resolved_store_id and items:
        for item in items:
            raw_name: str = (item.get("name") or "").strip()
            if not raw_name:
                continue

            # Recherche approximative du produit par nom (premiers 40 caractères)
            search_term = raw_name[:40]
            prod_res = await db.execute(
                select(Product)
                .where(
                    Product.name.ilike(f"%{search_term}%"),
                    Product.is_active == True,
                )
                .limit(1)
            )
            product = prod_res.scalar_one_or_none()
            if not product:
                continue

            # Prix unitaire (ou prix total si qté = 1)
            unit_price = item.get("unit_price") or item.get("total_price")
            if not unit_price or float(unit_price) <= 0:
                continue

            is_promo = bool(item.get("is_promo", False))

            price_record = Price(
                product_id=product.id,
                store_id=resolved_store_id,
                price=round(float(unit_price), 2),
                currency="MAD",
                source=PriceSource.OCR,
                is_promo=is_promo,
                promo_price=round(float(unit_price), 2) if is_promo else None,
                recorded_at=now,
            )
            db.add(price_record)
            saved_prices += 1

    # ── Marque le scan comme confirmé ─────────────────────────────────────────
    scan.parsed_data = {
        **parsed,
        "confirmed": True,
        "store_id": resolved_store_id,
        "prices_saved": saved_prices,
        "confirmed_at": now.isoformat(),
    }
    await db.commit()

    # Invalide le cache des produits impactés (les prix OCR sont prioritaires)
    if resolved_store_id and saved_prices > 0:
        await cache.invalidate_prefix("prixmaroc:prices:")
        await cache.invalidate_prefix("prixmaroc:products:search:")

    return {
        "status": "confirmed",
        "store_id": resolved_store_id,
        "store_matched": resolved_store_id is not None,
        "prices_saved": saved_prices,
        "message": (
            f"{saved_prices} prix enregistrés pour ce magasin."
            if saved_prices > 0
            else "Scan confirmé. Aucun produit matché en base — les prix seront affinés au fil du temps."
        ),
    }


@router.get("/scans", response_model=list[OcrScanRead])
async def list_scans(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retourne tous les scans de l'utilisateur connecté."""
    stmt = select(OcrScan).where(OcrScan.user_id == current_user.id).order_by(OcrScan.created_at.desc())
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/scan/{scan_id}", response_model=OcrScanRead)
async def get_scan(
    scan_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> OcrScanRead:
    """Récupère le résultat d'un scan précédent."""
    scan = await db.get(OcrScan, scan_id)
    if not scan or scan.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Scan introuvable")
    return OcrScanRead.model_validate(scan)
