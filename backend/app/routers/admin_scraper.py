"""
Interface admin — Gestion des scrapers.

Endpoints :
  POST   /admin/scrapers/{slug}/run       Déclenchement manuel immédiat
  GET    /admin/scrapers/                 Liste des configs + statut
  POST   /admin/scrapers/                 Ajouter une config (scraper générique)
  GET    /admin/scrapers/{slug}           Détail d'une config
  PUT    /admin/scrapers/{slug}           Modifier une config
  DELETE /admin/scrapers/{slug}           Supprimer une config
  GET    /admin/scrapers/{slug}/runs      Historique des runs
  GET    /admin/scrapers/{slug}/runs/{id} Détail d'un run + logs
  GET    /admin/scrapers/scheduler/jobs   Jobs APScheduler actifs
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect, status
from pydantic import BaseModel, Field
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db, AsyncSessionLocal
from app.models import ScraperConfig, ScraperRun, ScraperLog
from app.models.scraper import ScraperStatus
from app.services.scraper_service import ScraperOrchestrator, SCRAPER_REGISTRY
from app.services.scheduler import (
    get_scheduler, add_custom_job, remove_job, list_jobs, trigger_now,
)
from app.services.storage import get_storage_service
from app.utils.deps import get_superuser
from app.utils.security import decode_access_token

router = APIRouter(prefix="/admin/scrapers", tags=["admin — scrapers"])


# ──────────────────────────────────────────────────────────────────────────────
# Schémas Pydantic
# ──────────────────────────────────────────────────────────────────────────────

class ScraperConfigCreate(BaseModel):
    name: str
    slug: str
    base_url: str
    catalog_urls: list[str] = []
    selectors: dict = Field(default_factory=dict)
    rate_limit_seconds: float = 2.0
    schedule_cron: str = "0 3 * * *"
    store_images: bool = True
    is_active: bool = True


class ScraperConfigUpdate(BaseModel):
    name: str | None = None
    base_url: str | None = None
    catalog_urls: list[str] | None = None
    selectors: dict | None = None
    rate_limit_seconds: float | None = None
    schedule_cron: str | None = None
    store_images: bool | None = None
    is_active: bool | None = None


class ScraperConfigRead(BaseModel):
    id: int
    name: str
    slug: str
    base_url: str
    is_active: bool
    last_run_at: datetime | None
    last_status: ScraperStatus
    schedule_cron: str
    rate_limit_seconds: float
    model_config = {"from_attributes": True}


class ScraperRunRead(BaseModel):
    id: int
    config_id: int
    status: ScraperStatus
    triggered_by: str
    products_found: int
    products_new: int
    products_updated: int
    products_duplicate: int
    images_uploaded: int
    pages_scraped: int
    captcha_hits: int
    error_message: str | None
    started_at: datetime
    finished_at: datetime | None
    duration_seconds: float | None
    model_config = {"from_attributes": True}


class ScraperLogRead(BaseModel):
    id: int
    level: str
    message: str
    url: str | None
    created_at: datetime
    model_config = {"from_attributes": True}


# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

async def _get_config_or_404(slug: str, db: AsyncSession) -> ScraperConfig:
    result = await db.execute(select(ScraperConfig).where(ScraperConfig.slug == slug))
    config = result.scalar_one_or_none()
    if not config:
        # Auto-créer la config si le scraper est intégré (dans SCRAPER_REGISTRY)
        if slug in SCRAPER_REGISTRY:
            config = await _auto_create_config(slug, db)
        else:
            raise HTTPException(status_code=404, detail=f"Scraper '{slug}' introuvable")
    return config


# Métadonnées par défaut pour chaque scraper intégré
_BUILTIN_META: dict[str, dict] = {
    "marjane":   {"name": "Marjane",         "base_url": "https://www.marjane.ma",   "cron": "0 3 * * *",  "rate": 2.0},
    "carrefour": {"name": "Carrefour Maroc",  "base_url": "https://www.carrefour.ma", "cron": "20 3 * * *", "rate": 2.0},
    "labelvie":  {"name": "Label'Vie",        "base_url": "https://www.labelvie.ma",  "cron": "40 3 * * *", "rate": 2.0},
    "bim":       {"name": "BIM Maroc",        "base_url": "https://www.bim.ma",       "cron": "0 4 * * *",  "rate": 2.5},
    "kazyon":    {"name": "Kazyon Maroc",     "base_url": "https://www.kazyon.com",   "cron": "20 4 * * *", "rate": 2.0},
    "sopreco":   {"name": "Sopreco Atacadão", "base_url": "https://www.sopreco.ma",   "cron": "40 4 * * *", "rate": 2.0},
    "hmizate":   {"name": "Hmizate.ma",       "base_url": "https://hmizate.ma",       "cron": "0 5 * * *",  "rate": 3.0},
}


async def _auto_create_config(slug: str, db: AsyncSession) -> ScraperConfig:
    """Crée automatiquement la config en BDD pour un scraper intégré manquant."""
    meta = _BUILTIN_META.get(slug, {
        "name": slug.capitalize(),
        "base_url": f"https://www.{slug}.ma",
        "cron": "0 3 * * *",
        "rate": 2.0,
    })
    config = ScraperConfig(
        name=meta["name"],
        slug=slug,
        base_url=meta["base_url"],
        catalog_urls=[],
        selectors={},
        schedule_cron=meta["cron"],
        rate_limit_seconds=meta["rate"],
        store_images=True,
        is_active=True,
        last_status=ScraperStatus.IDLE,
    )
    db.add(config)
    await db.commit()
    await db.refresh(config)
    return config


async def _run_and_persist(
    slug: str,
    config_dict: dict | None,
    triggered_by: str,
    db: AsyncSession,
) -> ScraperRun:
    """Exécute le scraper et persiste le run + logs en BDD."""
    run_logs: list[str] = []

    # Création du run
    scraper_config = await _get_config_or_404(slug, db)
    run = ScraperRun(
        config_id=scraper_config.id,
        triggered_by=triggered_by,
        status=ScraperStatus.RUNNING,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)

    # Mise à jour config
    scraper_config.last_run_at = datetime.now(timezone.utc)
    scraper_config.last_status = ScraperStatus.RUNNING
    await db.commit()

    storage = get_storage_service()
    orchestrator = ScraperOrchestrator(db=db, storage=storage)

    try:
        result = await orchestrator.run(slug, triggered_by=triggered_by, config=config_dict)

        run.status = ScraperStatus.SUCCESS
        run.products_found = len(result.products)
        run.pages_scraped = result.pages_scraped
        run.captcha_hits = result.captcha_hits
        run.finished_at = datetime.now(timezone.utc)
        run.duration_seconds = result.duration_seconds

        if result.captcha_hits > 0:
            run.status = ScraperStatus.CAPTCHA

        scraper_config.last_status = run.status

    except Exception as exc:
        run.status = ScraperStatus.FAILED
        run.error_message = str(exc)
        run.finished_at = datetime.now(timezone.utc)
        scraper_config.last_status = ScraperStatus.FAILED
        run_logs.append(f"[ERROR] {exc}")

    # Persistance des logs
    for msg in run_logs:
        level = "ERROR" if msg.startswith("[ERROR]") else "WARN" if msg.startswith("[CAPTCHA]") else "INFO"
        db.add(ScraperLog(run_id=run.id, level=level, message=msg))

    await db.commit()
    await db.refresh(run)
    return run


# ──────────────────────────────────────────────────────────────────────────────
# Endpoints
# ──────────────────────────────────────────────────────────────────────────────

@router.get("/scheduler/jobs", summary="Jobs APScheduler actifs")
async def get_scheduler_jobs(_=Depends(get_superuser)) -> list[dict]:
    return list_jobs(get_scheduler())


@router.get("/status", summary="Statut de tous les scrapers (panel admin web)")
async def get_all_scrapers_status(
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    """Retourne le statut de chaque scraper connu pour le dashboard admin."""
    result = await db.execute(select(ScraperConfig))
    configs = result.scalars().all()
    return {
        c.slug: {
            "status": c.last_status.value if c.last_status else "unknown",
            "last_run": c.last_run_at.isoformat() if c.last_run_at else None,
            "products_count": None,  # rempli par le dernier run
        }
        for c in configs
    }


@router.post("/{slug}/trigger", summary="Déclencher un scraper (alias pour le panel admin web)")
async def trigger_scraper_alias(
    slug: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    """Alias de /{slug}/run pour compatibilité avec le panel admin React."""
    config = await _get_config_or_404(slug, db)
    config_dict = None
    if slug not in SCRAPER_REGISTRY:
        config_dict = {
            "base_url": config.base_url,
            "catalog_urls": config.catalog_urls or [],
            "selectors": config.selectors or {},
            "rate_limit_seconds": config.rate_limit_seconds,
        }
    background_tasks.add_task(trigger_now, slug, config_dict)
    return {"slug": slug, "status": "triggered", "message": f"Scraper '{slug}' démarré"}


@router.get("/", response_model=list[ScraperConfigRead], summary="Liste des scrapers")
async def list_scrapers(
    active_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    stmt = select(ScraperConfig)
    if active_only:
        stmt = stmt.where(ScraperConfig.is_active == True)
    result = await db.execute(stmt.order_by(ScraperConfig.name))
    return result.scalars().all()


@router.post("/", response_model=ScraperConfigRead, status_code=status.HTTP_201_CREATED,
             summary="Ajouter un scraper générique")
async def create_scraper(
    payload: ScraperConfigCreate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    existing = await db.execute(select(ScraperConfig).where(ScraperConfig.slug == payload.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Slug '{payload.slug}' déjà utilisé")

    config = ScraperConfig(**payload.model_dump())
    db.add(config)
    await db.commit()
    await db.refresh(config)

    # Enregistrer dans le scheduler
    add_custom_job(
        get_scheduler(),
        slug=payload.slug,
        cron=payload.schedule_cron,
        config=payload.model_dump(),
    )
    return config


@router.get("/{slug}", response_model=ScraperConfigRead, summary="Détail d'un scraper")
async def get_scraper(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    return await _get_config_or_404(slug, db)


@router.put("/{slug}", response_model=ScraperConfigRead, summary="Modifier un scraper")
async def update_scraper(
    slug: str,
    payload: ScraperConfigUpdate,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    config = await _get_config_or_404(slug, db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(config, field, value)
    await db.commit()
    await db.refresh(config)

    # Mise à jour du schedule si modifié
    if payload.schedule_cron:
        add_custom_job(get_scheduler(), slug=slug, cron=payload.schedule_cron)

    return config


@router.delete("/{slug}", status_code=status.HTTP_204_NO_CONTENT, summary="Supprimer un scraper")
async def delete_scraper(
    slug: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    config = await _get_config_or_404(slug, db)
    remove_job(get_scheduler(), slug)
    await db.delete(config)
    await db.commit()


@router.post("/{slug}/run", summary="Déclencher un scraping manuel")
async def run_scraper_now(
    slug: str,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    """
    Lance le scraper immédiatement en tâche de fond.
    Retourne l'ID du run pour suivi via GET /{slug}/runs/{id}.
    """
    config = await _get_config_or_404(slug, db)
    if config.last_status == ScraperStatus.RUNNING:
        raise HTTPException(status_code=409, detail="Ce scraper est déjà en cours d'exécution")

    config_dict = None
    if slug not in SCRAPER_REGISTRY:
        config_dict = {
            "base_url": config.base_url,
            "catalog_urls": config.catalog_urls or [],
            "selectors": config.selectors or {},
            "rate_limit_seconds": config.rate_limit_seconds,
        }

    # Création anticipée du run pour retourner l'ID
    run = ScraperRun(config_id=config.id, triggered_by="admin", status=ScraperStatus.RUNNING)
    db.add(run)
    await db.commit()
    await db.refresh(run)

    config.last_status = ScraperStatus.RUNNING
    config.last_run_at = datetime.now(timezone.utc)
    await db.commit()

    background_tasks.add_task(trigger_now, slug, config_dict)

    return {
        "run_id": run.id,
        "slug": slug,
        "status": "started",
        "message": f"Scraper '{slug}' démarré en arrière-plan",
    }


@router.get("/{slug}/runs", response_model=list[ScraperRunRead], summary="Historique des runs")
async def list_runs(
    slug: str,
    limit: int = Query(default=20, le=100),
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    config = await _get_config_or_404(slug, db)
    result = await db.execute(
        select(ScraperRun)
        .where(ScraperRun.config_id == config.id)
        .order_by(desc(ScraperRun.started_at))
        .limit(limit)
    )
    return result.scalars().all()


@router.websocket("/{slug}/logs/stream")
async def stream_scraper_logs_ws(
    slug: str,
    websocket: WebSocket,
    token: str | None = Query(default=None),
):
    """WebSocket — stream des logs en temps réel pour le dernier run d'un scraper."""
    # Vérification du token
    if not token:
        await websocket.close(code=1008, reason="Token manquant")
        return
    try:
        decode_access_token(token)
    except Exception:
        await websocket.close(code=1008, reason="Token invalide")
        return

    await websocket.accept()
    last_log_id: int = 0
    last_run_id: int | None = None

    try:
        while True:
            async with AsyncSessionLocal() as db:
                # Récupère la config
                cfg_r = await db.execute(select(ScraperConfig).where(ScraperConfig.slug == slug))
                config = cfg_r.scalar_one_or_none()
                if not config:
                    await websocket.send_json({"type": "error", "message": f"Scraper '{slug}' introuvable"})
                    break

                # Dernier run
                run_r = await db.execute(
                    select(ScraperRun)
                    .where(ScraperRun.config_id == config.id)
                    .order_by(desc(ScraperRun.started_at))
                    .limit(1)
                )
                run = run_r.scalar_one_or_none()

                if run:
                    # Reset si nouveau run détecté
                    if last_run_id and run.id != last_run_id:
                        last_log_id = 0
                    last_run_id = run.id

                    # Nouveaux logs depuis le dernier id vu
                    logs_r = await db.execute(
                        select(ScraperLog)
                        .where(ScraperLog.run_id == run.id, ScraperLog.id > last_log_id)
                        .order_by(ScraperLog.created_at)
                        .limit(50)
                    )
                    new_logs = logs_r.scalars().all()

                    for log in new_logs:
                        last_log_id = log.id
                        await websocket.send_json({
                            "type": "log",
                            "level": log.level,
                            "message": log.message,
                            "url": log.url,
                            "time": log.created_at.isoformat(),
                        })

                    # Envoi du statut courant
                    await websocket.send_json({
                        "type": "status",
                        "status": run.status.value,
                        "run_id": run.id,
                        "products_found": run.products_found,
                        "pages_scraped": run.pages_scraped,
                    })

                    # Fin du run : on attend les derniers logs puis on ferme
                    if run.status in (ScraperStatus.SUCCESS, ScraperStatus.FAILED, ScraperStatus.CAPTCHA):
                        if not new_logs:
                            await websocket.send_json({"type": "done", "status": run.status.value})
                            break
                else:
                    await websocket.send_json({"type": "heartbeat"})

            await asyncio.sleep(1.5)

    except WebSocketDisconnect:
        pass
    except Exception as exc:
        try:
            await websocket.send_json({"type": "error", "message": str(exc)})
        except Exception:
            pass
    finally:
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/{slug}/runs/{run_id}", summary="Détail d'un run + logs")
async def get_run_detail(
    slug: str,
    run_id: int,
    db: AsyncSession = Depends(get_db),
    _=Depends(get_superuser),
):
    config = await _get_config_or_404(slug, db)
    run = await db.get(ScraperRun, run_id)
    if not run or run.config_id != config.id:
        raise HTTPException(status_code=404, detail="Run introuvable")

    logs_result = await db.execute(
        select(ScraperLog)
        .where(ScraperLog.run_id == run_id)
        .order_by(ScraperLog.created_at)
        .limit(500)
    )
    logs = logs_result.scalars().all()

    return {
        "run": ScraperRunRead.model_validate(run),
        "logs": [ScraperLogRead.model_validate(log) for log in logs],
    }
