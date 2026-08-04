"""
Scheduler APScheduler — Scraping automatique quotidien à 3h du matin.

Utilise AsyncIOScheduler (compatible avec FastAPI/asyncio).
Chaque scraper est déclenché selon son schedule_cron en BDD.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.executors.asyncio import AsyncIOExecutor

from app.services.scraper_service import ScraperOrchestrator, SCRAPER_REGISTRY
from app.services.storage import get_storage_service
from app.db import AsyncSessionLocal
from app.services.notification_service import notification_service, PushNotification
from app.services.store_updater import run_update as _store_run_update

# ──────────────────────────────────────────────────────────────────────────────
# Règle : max 2 notifications push par utilisateur par jour
# Stocké dans Redis : clé "notif_daily:{date}:{token}" → count (int)
# ──────────────────────────────────────────────────────────────────────────────

MAX_NOTIFS_PER_DAY = 2


async def _filter_tokens_by_daily_limit(tokens: list[str]) -> list[str]:
    """
    Filtre les tokens : ne garde que ceux qui n'ont pas encore reçu
    MAX_NOTIFS_PER_DAY notifications aujourd'hui.
    Met à jour les compteurs dans Redis.
    """
    try:
        from app.utils.cache import cache
        from datetime import date

        today = date.today().isoformat()
        allowed: list[str] = []

        for token in tokens:
            # Clé Redis unique par token et par jour
            key = f"notif_daily:{today}:{token[-16:]}"  # 16 derniers chars du token
            raw = await cache.get(key)
            count = int(raw) if raw is not None else 0

            if count < MAX_NOTIFS_PER_DAY:
                allowed.append(token)
                # Incrémenter le compteur, TTL = 26h (couvre le jour + marge)
                await cache.set(key, count + 1, ttl=93600)

        logger.info(
            f"[Scheduler] Quota notifs: {len(allowed)}/{len(tokens)} tokens autorisés"
            f" (max {MAX_NOTIFS_PER_DAY}/jour)"
        )
        return allowed

    except Exception as exc:
        # En cas d'erreur Redis, on envoie à tous (fail open)
        logger.warning(f"[Scheduler] Quota Redis indisponible, envoi sans filtre: {exc}")
        return tokens

logger = logging.getLogger("prixmaroc.scheduler")


# ──────────────────────────────────────────────────────────────────────────────
# Singleton scheduler
# ──────────────────────────────────────────────────────────────────────────────

_scheduler: AsyncIOScheduler | None = None


def get_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = AsyncIOScheduler(
            jobstores={"default": MemoryJobStore()},
            executors={"default": AsyncIOExecutor()},
            job_defaults={"coalesce": True, "max_instances": 1, "misfire_grace_time": 3600},
            timezone="Africa/Casablanca",
        )
    return _scheduler


# ──────────────────────────────────────────────────────────────────────────────
# Jobs de scraping
# ──────────────────────────────────────────────────────────────────────────────

async def _run_scraper_job(slug: str, config: dict | None = None) -> None:
    """Tâche exécutée par le scheduler pour un scraper donné."""
    logger.info(f"[Scheduler] Démarrage job scraper : {slug}")
    storage = get_storage_service()
    orchestrator = ScraperOrchestrator(storage=storage)
    try:
        result = await orchestrator.run(slug, triggered_by="scheduler", config=config)
        logger.info(
            f"[Scheduler] Job '{slug}' terminé — "
            f"{len(result.products)} produits, "
            f"{result.pages_scraped} pages, "
            f"durée={result.duration_seconds:.1f}s"
        )
    except Exception as exc:
        logger.error(f"[Scheduler] Job '{slug}' échoué : {exc}", exc_info=True)


# ──────────────────────────────────────────────────────────────────────────────
# Jobs de notifications push
# ──────────────────────────────────────────────────────────────────────────────

async def _job_liste_hebdo() -> None:
    """Dimanche 9h — Rappel liste de courses hebdomadaire."""
    logger.info("[Scheduler] Job: liste hebdomadaire")
    try:
        from sqlalchemy import select
        from app.models import User
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User.fcm_token).where(
                    User.fcm_token.isnot(None),
                    User.is_active == True,
                )
            )
            tokens = [row[0] for row in result.fetchall()]
        if tokens:
            tokens = await _filter_tokens_by_daily_limit(tokens)
        if tokens:
            notif = PushNotification(
                title="🛒 C'est l'heure de vos courses !",
                body="Planifiez votre semaine avec votre liste PrixMaroc personnalisée.",
                notif_type="LISTE_RAPPEL",
                data={"screen": "NouvelleListeIA"},
            )
            sent = await notification_service.send_to_multiple(tokens, notif)
            logger.info(f"[Scheduler] Liste hebdo envoyée à {sent}/{len(tokens)} utilisateurs")
    except Exception as exc:
        logger.error(f"[Scheduler] Job liste hebdo échoué: {exc}", exc_info=True)


async def _job_promos_quotidiennes() -> None:
    """Chaque jour 8h — Alertes promos du jour."""
    logger.info("[Scheduler] Job: promos quotidiennes")
    try:
        from sqlalchemy import select, func
        from app.models import User, Price
        async with AsyncSessionLocal() as db:
            count_result = await db.execute(
                select(func.count(Price.id)).where(
                    Price.is_promo == True,
                    func.date(Price.recorded_at) == func.current_date(),
                )
            )
            promo_count = count_result.scalar_one_or_none() or 0
            if promo_count == 0:
                logger.info("[Scheduler] Pas de promos aujourd'hui, notification annulée")
                return
            result = await db.execute(
                select(User.fcm_token).where(
                    User.fcm_token.isnot(None),
                    User.is_active == True,
                )
            )
            tokens = [row[0] for row in result.fetchall()]
        if tokens:
            tokens = await _filter_tokens_by_daily_limit(tokens)
        if tokens:
            notif = PushNotification(
                title=f"🔥 {promo_count} promotions aujourd'hui !",
                body="Des produits de votre liste sont en promo. Consultez-les maintenant.",
                notif_type="PRIX_BAISSE",
                data={"screen": "Promotions"},
            )
            sent = await notification_service.send_to_multiple(tokens, notif)
            logger.info(f"[Scheduler] Promos envoyées à {sent}/{len(tokens)} utilisateurs")
    except Exception as exc:
        logger.error(f"[Scheduler] Job promos quotidiennes échoué: {exc}", exc_info=True)


async def _job_bilan_economies() -> None:
    """Lundi 7h — Bilan économies de la semaine."""
    logger.info("[Scheduler] Job: bilan économies hebdo")
    try:
        from sqlalchemy import select
        from app.models import User
        async with AsyncSessionLocal() as db:
            result = await db.execute(
                select(User.fcm_token).where(
                    User.fcm_token.isnot(None),
                    User.is_active == True,
                )
            )
            tokens = [row[0] for row in result.fetchall()]
        if tokens:
            tokens = await _filter_tokens_by_daily_limit(tokens)
        if tokens:
            notif = PushNotification(
                title="📊 Votre bilan économies",
                body="Découvrez combien vous avez économisé cette semaine grâce à PrixMaroc.",
                notif_type="ECONOMIE_HEBDO",
                data={"screen": "MonProfil"},
            )
            sent = await notification_service.send_to_multiple(tokens, notif)
            logger.info(f"[Scheduler] Bilan éco envoyé à {sent}/{len(tokens)} utilisateurs")
    except Exception as exc:
        logger.error(f"[Scheduler] Job bilan éco échoué: {exc}", exc_info=True)


# ──────────────────────────────────────────────────────────────────────────────
# Job de mise à jour des magasins (hebdomadaire)
# ──────────────────────────────────────────────────────────────────────────────

async def _job_update_stores() -> None:
    """Lundi 2h — Mise à jour des magasins depuis OSM + store locators."""
    logger.info("[Scheduler] Job: mise à jour automatique des magasins")
    try:
        result = await _store_run_update(sources=["osm", "locator"])
        logger.info(
            f"[Scheduler] MAJ magasins terminée — "
            f"{result.get('inserted', 0)} insérés, "
            f"{result.get('updated', 0)} mis à jour, "
            f"{result.get('after_dedup', 0)} total après dédup"
        )
    except Exception as exc:
        logger.error(f"[Scheduler] Job update_stores échoué : {exc}", exc_info=True)


# ──────────────────────────────────────────────────────────────────────────────
# Gestion du cycle de vie (startup / shutdown)
# ──────────────────────────────────────────────────────────────────────────────

def register_default_jobs(scheduler: AsyncIOScheduler) -> None:
    """
    Enregistre les jobs par défaut pour les 3 enseignes principales.
    Chaque enseigne scrappe à 3h du matin, décalées de 20 min pour ne pas saturer.
    """
    jobs = [
        ("marjane",   "0 3 * * *"),   # 03:00 Africa/Casablanca
        ("carrefour", "20 3 * * *"),  # 03:20
        ("labelvie",  "40 3 * * *"),  # 03:40
        ("bim",       "0 4 * * *"),   # 04:00
        ("kazyon",    "20 4 * * *"),  # 04:20
        ("sopreco",   "40 4 * * *"),  # 04:40
        ("hmizate",   "0 5 * * *"),   # 05:00 — agrégateur bons plans
    ]

    for slug, cron in jobs:
        scheduler.add_job(
            _run_scraper_job,
            trigger=CronTrigger.from_crontab(cron, timezone="Africa/Casablanca"),
            id=f"scraper_{slug}",
            name=f"Scraper {slug.capitalize()}",
            args=[slug],
            replace_existing=True,
        )
        logger.info(f"[Scheduler] Job '{slug}' enregistré (cron: {cron})")

    # Jobs notifications push
    scheduler.add_job(
        _job_liste_hebdo,
        trigger=CronTrigger.from_crontab("0 9 * * 0", timezone="Africa/Casablanca"),
        id="notif_liste_hebdo",
        name="Notification — Liste hebdomadaire",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_promos_quotidiennes,
        trigger=CronTrigger.from_crontab("0 8 * * *", timezone="Africa/Casablanca"),
        id="notif_promos_quotidiennes",
        name="Notification — Promos quotidiennes",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_bilan_economies,
        trigger=CronTrigger.from_crontab("0 7 * * 1", timezone="Africa/Casablanca"),
        id="notif_bilan_economies",
        name="Notification — Bilan économies",
        replace_existing=True,
    )
    logger.info("[Scheduler] 3 jobs notifications enregistrés")

    # Job hebdomadaire — mise à jour automatique des magasins (lundi 2h)
    scheduler.add_job(
        _job_update_stores,
        trigger=CronTrigger.from_crontab("0 2 * * 1", timezone="Africa/Casablanca"),
        id="update_stores",
        name="Mise à jour automatique magasins (OSM + Store Locators)",
        replace_existing=True,
    )
    logger.info("[Scheduler] Job 'update_stores' enregistré (tous les lundis à 02:00)")


def add_custom_job(
    scheduler: AsyncIOScheduler,
    slug: str,
    cron: str,
    config: dict | None = None,
) -> str:
    """Ajoute un job de scraping personnalisé (depuis l'admin)."""
    job_id = f"scraper_{slug}"
    scheduler.add_job(
        _run_scraper_job,
        trigger=CronTrigger.from_crontab(cron, timezone="Africa/Casablanca"),
        id=job_id,
        name=f"Scraper {slug}",
        args=[slug, config],
        replace_existing=True,
    )
    logger.info(f"[Scheduler] Job custom '{slug}' ajouté (cron: {cron})")
    return job_id


def remove_job(scheduler: AsyncIOScheduler, slug: str) -> bool:
    job_id = f"scraper_{slug}"
    try:
        scheduler.remove_job(job_id)
        logger.info(f"[Scheduler] Job '{slug}' supprimé")
        return True
    except Exception:
        return False


def list_jobs(scheduler: AsyncIOScheduler) -> list[dict]:
    """Retourne la liste des jobs actifs avec leur prochain déclenchement."""
    jobs = []
    for job in scheduler.get_jobs():
        jobs.append({
            "id": job.id,
            "name": job.name,
            "next_run": job.next_run_time.isoformat() if job.next_run_time else None,
            "trigger": str(job.trigger),
        })
    return jobs


async def trigger_now(slug: str, config: dict | None = None) -> None:
    """Déclenche un scraper immédiatement (depuis l'admin)."""
    logger.info(f"[Scheduler] Déclenchement manuel : {slug}")
    await _run_scraper_job(slug, config)


# ──────────────────────────────────────────────────────────────────────────────
# Intégration FastAPI (lifespan)
# ──────────────────────────────────────────────────────────────────────────────

def startup_scheduler() -> AsyncIOScheduler:
    """À appeler dans le lifespan FastAPI (startup)."""
    scheduler = get_scheduler()
    register_default_jobs(scheduler)
    scheduler.start()
    logger.info("[Scheduler] Démarré — timezone=Africa/Casablanca")
    return scheduler


def shutdown_scheduler() -> None:
    """À appeler dans le lifespan FastAPI (shutdown)."""
    scheduler = get_scheduler()
    if scheduler.running:
        scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Arrêté")
