"""
Initialise les configurations des scrapers dans la base de données.

Usage:
    python seed_scraper_configs.py

Ce script crée (si absents) les enregistrements ScraperConfig pour
tous les scrapers connus. À exécuter une seule fois après la première
migration de la base.
"""
from __future__ import annotations

import asyncio
import logging
import sys

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

sys.path.insert(0, "/app")

from app.core.config import settings
from app.models.scraper import ScraperConfig, ScraperStatus

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed_scrapers")

# ──────────────────────────────────────────────────────────────────────────────
# Définitions des scrapers
# ──────────────────────────────────────────────────────────────────────────────

SCRAPER_CONFIGS = [
    {
        "name": "Marjane",
        "slug": "marjane",
        "base_url": "https://www.marjane.ma",
        "catalog_urls": [
            "/fr/alimentation", "/fr/boissons", "/fr/produits-frais",
            "/fr/epicerie", "/fr/hygiene-beaute", "/fr/entretien-maison",
        ],
        "schedule_cron": "0 3 * * *",
        "rate_limit_seconds": 2.0,
        "store_images": True,
        "is_active": True,
    },
    {
        "name": "Carrefour Maroc",
        "slug": "carrefour",
        "base_url": "https://www.carrefour.ma",
        "catalog_urls": [
            "/epicerie", "/frais", "/surgeles",
            "/hygiene-beaute", "/entretien", "/boissons",
        ],
        "schedule_cron": "20 3 * * *",
        "rate_limit_seconds": 2.0,
        "store_images": True,
        "is_active": True,
    },
    {
        "name": "Label'Vie",
        "slug": "labelvie",
        "base_url": "https://www.labelvie.ma",
        "catalog_urls": [
            "/epicerie", "/boissons", "/produits-frais",
            "/hygiene-beaute", "/entretien", "/promotions",
        ],
        "schedule_cron": "40 3 * * *",
        "rate_limit_seconds": 2.0,
        "store_images": True,
        "is_active": True,
    },
    {
        "name": "BIM Maroc",
        "slug": "bim",
        "base_url": "https://www.bim.ma",
        "catalog_urls": [
            "/fr/produits/alimentation", "/fr/produits/boissons",
            "/fr/produits/hygiene-beaute", "/fr/produits/entretien",
            "/fr/produits/frais", "/fr/promotions",
        ],
        "schedule_cron": "0 4 * * *",
        "rate_limit_seconds": 2.5,
        "store_images": True,
        "is_active": True,
    },
    {
        "name": "Kazyon Maroc",
        "slug": "kazyon",
        "base_url": "https://www.kazyon.com",
        "catalog_urls": [
            "/ma/alimentation", "/ma/boissons", "/ma/hygiene",
            "/ma/entretien", "/ma/epicerie", "/ma/promotions",
        ],
        "schedule_cron": "20 4 * * *",
        "rate_limit_seconds": 2.0,
        "store_images": True,
        "is_active": True,
    },
    {
        "name": "Sopreco (Atacadão)",
        "slug": "sopreco",
        "base_url": "https://www.sopreco.ma",
        "catalog_urls": [
            "/alimentation", "/boissons", "/produits-laitiers",
            "/hygiene-beaute", "/entretien-menager",
            "/epicerie-salee", "/promotions",
        ],
        "schedule_cron": "40 4 * * *",
        "rate_limit_seconds": 2.0,
        "store_images": True,
        "is_active": True,
    },
    {
        "name": "Hmizate.ma",
        "slug": "hmizate",
        "base_url": "https://hmizate.ma",
        "catalog_urls": [
            "/bons-plans/alimentaire", "/bons-plans/epicerie",
            "/bons-plans/hygiene-beaute", "/bons-plans/entretien-maison",
            "/bons-plans/boissons", "/bons-plans/frais-surgeles",
            "/promotions", "/catalogues",
        ],
        "schedule_cron": "0 5 * * *",
        "rate_limit_seconds": 3.0,
        "store_images": True,
        "is_active": True,
    },
]


async def seed_scraper_configs(db: AsyncSession) -> None:
    log.info("── Configurations scrapers ──────────────────────")

    result = await db.execute(select(ScraperConfig.slug))
    existing_slugs: set[str] = {row[0] for row in result}

    inserted = 0
    skipped = 0

    for cfg in SCRAPER_CONFIGS:
        if cfg["slug"] in existing_slugs:
            log.info(f"  ↷ '{cfg['slug']}' déjà présent — ignoré")
            skipped += 1
            continue

        config = ScraperConfig(
            name=cfg["name"],
            slug=cfg["slug"],
            base_url=cfg["base_url"],
            catalog_urls=cfg["catalog_urls"],
            selectors={},
            schedule_cron=cfg["schedule_cron"],
            rate_limit_seconds=cfg["rate_limit_seconds"],
            store_images=cfg.get("store_images", True),
            is_active=cfg.get("is_active", True),
            last_status=ScraperStatus.IDLE,
        )
        db.add(config)
        log.info(f"  ✓ '{cfg['slug']}' ajouté")
        inserted += 1

    await db.commit()
    log.info(f"\n  Résultat : {inserted} insérés, {skipped} déjà présents")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        await seed_scraper_configs(db)

    await engine.dispose()
    log.info("✅ Terminé.")


if __name__ == "__main__":
    asyncio.run(main())
