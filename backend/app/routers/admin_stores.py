"""
Admin — Gestion et mise à jour des magasins.

Endpoints :
  POST /admin/stores/update          Déclenche la MAJ depuis OSM + locators
  GET  /admin/stores/update/status   Statut de la dernière MAJ
  GET  /admin/stores                 Liste paginée des magasins (admin)
  PATCH /admin/stores/{id}           Mise à jour d'un magasin
  DELETE /admin/stores/{id}          Désactivation d'un magasin
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy import select, func, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.deps import get_db, get_superuser
from app.models import Store
from app.services.store_updater import run_update

logger = logging.getLogger("prixmaroc.admin_stores")

router = APIRouter(prefix="/admin/stores", tags=["admin-stores"])

# ──────────────────────────────────────────────────────────────────────────────
# État de la dernière mise à jour (en mémoire — suffisant)
# ──────────────────────────────────────────────────────────────────────────────

_last_update_result: dict[str, Any] | None = None
_update_running: bool = False
_update_started_at: datetime | None = None


# ──────────────────────────────────────────────────────────────────────────────
# Schémas
# ──────────────────────────────────────────────────────────────────────────────

class UpdateRequest(BaseModel):
    sources: list[str] = ["osm", "locator"]  # "osm", "locator", "all"


class StoreUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    region: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    phone: Optional[str] = None
    website: Optional[str] = None
    logo_url: Optional[str] = None
    is_active: Optional[bool] = None


# ──────────────────────────────────────────────────────────────────────────────
# Background task wrapper
# ──────────────────────────────────────────────────────────────────────────────

async def _run_update_background(sources: list[str]) -> None:
    global _update_running, _last_update_result, _update_started_at
    _update_running = True
    _update_started_at = datetime.now(timezone.utc)
    try:
        result = await run_update(sources=sources)
        result["started_at"] = _update_started_at.isoformat()
        result["finished_at"] = datetime.now(timezone.utc).isoformat()
        result["status"] = "success"
        _last_update_result = result
        logger.info(f"[AdminStores] MAJ terminée : {result}")
    except Exception as exc:
        _last_update_result = {
            "status": "error",
            "error": str(exc),
            "started_at": _update_started_at.isoformat() if _update_started_at else None,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.error(f"[AdminStores] MAJ échouée : {exc}", exc_info=True)
    finally:
        _update_running = False


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.post("/update", summary="Déclenche la mise à jour des magasins (OSM + locators)")
async def trigger_store_update(
    payload: UpdateRequest,
    background_tasks: BackgroundTasks,
    _: Any = Depends(get_superuser),
):
    """
    Lance la mise à jour en arrière-plan.
    Retourne immédiatement avec un statut 202 Accepted.
    Appelez GET /admin/stores/update/status pour suivre l'avancement.
    """
    global _update_running
    if _update_running:
        raise HTTPException(status_code=409, detail="Une mise à jour est déjà en cours")

    sources = payload.sources
    if "all" in sources:
        sources = ["osm", "locator"]

    background_tasks.add_task(_run_update_background, sources)
    return {
        "status": "accepted",
        "message": f"Mise à jour lancée en arrière-plan (sources: {', '.join(sources)})",
        "sources": sources,
    }


@router.get("/update/status", summary="Statut de la dernière mise à jour des magasins")
async def get_update_status(
    _: Any = Depends(get_superuser),
):
    return {
        "running": _update_running,
        "started_at": _update_started_at.isoformat() if _update_started_at else None,
        "last_result": _last_update_result,
    }


@router.get("", summary="Liste paginée des magasins (admin)")
async def list_stores_admin(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(get_superuser),
):
    stmt = select(Store)
    if search:
        stmt = stmt.where(
            or_(
                Store.name.ilike(f"%{search}%"),
                Store.city.ilike(f"%{search}%"),
                Store.address.ilike(f"%{search}%"),
            )
        )
    if city:
        stmt = stmt.where(Store.city.ilike(f"%{city}%"))
    if active_only:
        stmt = stmt.where(Store.is_active == True)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total_result = await db.execute(count_stmt)
    total = total_result.scalar_one()

    stmt = stmt.order_by(Store.city, Store.name).offset(skip).limit(limit)
    result = await db.execute(stmt)
    stores = result.scalars().all()

    return {
        "total": total,
        "skip": skip,
        "limit": limit,
        "stores": [
            {
                "id": s.id,
                "name": s.name,
                "slug": s.slug,
                "city": s.city,
                "region": s.region,
                "address": s.address,
                "latitude": s.latitude,
                "longitude": s.longitude,
                "phone": s.phone,
                "website": s.website,
                "logo_url": s.logo_url,
                "is_active": s.is_active,
            }
            for s in stores
        ],
    }


@router.patch("/{store_id}", summary="Mise à jour d'un magasin")
async def update_store(
    store_id: int,
    payload: StoreUpdate,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(get_superuser),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Magasin introuvable")

    update_data = payload.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(store, key, value)

    await db.commit()
    await db.refresh(store)
    return {"id": store.id, "name": store.name, "updated": True}


@router.delete("/{store_id}", summary="Désactive un magasin (soft delete)")
async def deactivate_store(
    store_id: int,
    db: AsyncSession = Depends(get_db),
    _: Any = Depends(get_superuser),
):
    store = await db.get(Store, store_id)
    if not store:
        raise HTTPException(status_code=404, detail="Magasin introuvable")
    store.is_active = False
    await db.commit()
    return {"id": store.id, "is_active": False, "message": "Magasin désactivé"}
