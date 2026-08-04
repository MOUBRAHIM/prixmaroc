"""
Script de scraping direct — récupère les vrais prix depuis les sites marocains
et les insère dans la base de données PrixMaroc.

Usage: python run_scrapers.py [marjane] [labelvie] [bim] [all]
"""
from __future__ import annotations

import asyncio
import logging
import re
import sys
from datetime import datetime, timezone

import asyncpg

# ── Configuration ─────────────────────────────────────────────────────────────
DATABASE_URL = "postgresql://prixmaroc:prixmaroc@db:5432/prixmaroc"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("run_scrapers")


# ── Import des scrapers ───────────────────────────────────────────────────────
import sys, os
sys.path.insert(0, "/app")

from app.services.scraper_service import (
    MarjaneScraper, LabelVieScraper, BimScraper,
    ScrapedProduct, ScrapeResult, SCRAPER_REGISTRY,
)


# ── Map slug scraper → store slug en base ─────────────────────────────────────
# Pour hmizate (agrégateur multi-enseignes), on utilise "hmizate" comme store
# virtuel ou on détecte l'enseigne depuis le champ brand du produit scrapé.
SCRAPER_TO_STORE = {
    "marjane":   "marjane-casa",
    "carrefour": "carrefour-casa",
    "labelvie":  "labelvie-casa",
    "bim":       "bim-casa",
    "kazyon":    "kazyon-sidi-moumen",
    "sopreco":   "sopreco-casa",
    "hmizate":   None,  # agrégateur — store détecté depuis product.brand
}

# Map enseigne (brand) → store slug pour hmizate
HMIZATE_BRAND_TO_STORE: dict[str, str] = {
    "marjane":   "marjane-casa",
    "carrefour": "carrefour-casa",
    "labelvie":  "labelvie-casa",
    "label'vie": "labelvie-casa",
    "bim":       "bim-casa",
    "kazyon":    "kazyon-sidi-moumen",
    "sopreco":   "sopreco-casa",
    "atacadao":  "sopreco-casa",
}

# ── Map catégorie scrapée → category_id en base ────────────────────────────────
CATEGORY_KEYWORDS = {
    "alimentation":    1,
    "alimentaire":     1,
    "épicerie":        1,
    "epicerie":        1,
    "produits frais":  2,
    "frais":           2,
    "lait":            2,
    "dairy":           2,
    "boisson":         3,
    "boissons":        3,
    "jus":             3,
    "eau":             3,
    "hygiène":         4,
    "hygiene":         4,
    "beauté":          4,
    "beaute":          4,
    "entretien":       5,
    "nettoyage":       5,
    "boulanger":       6,
    "pain":            6,
    "viande":          7,
    "poisson":         7,
    "surgelé":         7,
    "congel":          7,
    "bébé":            8,
    "bebe":            8,
}


def guess_category(name: str, cat: str | None) -> int | None:
    text = ((cat or "") + " " + name).lower()
    for keyword, cat_id in CATEGORY_KEYWORDS.items():
        if keyword in text:
            return cat_id
    return 1  # default: alimentation


def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[àâä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[îï]", "i", text)
    text = re.sub(r"[ôö]", "o", text)
    text = re.sub(r"[ùûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:490]


async def persist_products(
    conn: asyncpg.Connection,
    products: list[ScrapedProduct],
    store_id: int,
) -> tuple[int, int]:
    """Insère ou met à jour les produits et prix. Retourne (n_new, n_updated)."""
    n_new = 0
    n_updated = 0

    for p in products:
        if not p.name or p.price <= 0:
            continue

        slug = slugify(p.name)
        cat_id = guess_category(p.name, p.category)

        # Upsert produit
        existing_id = await conn.fetchval(
            "SELECT id FROM products WHERE slug = $1", slug
        )

        if existing_id is None:
            # Insérer nouveau produit
            product_id = await conn.fetchval(
                """INSERT INTO products (name, slug, brand, image_url, unit, category_id, is_active)
                   VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                   RETURNING id""",
                p.name, slug, p.brand, p.image_url, p.unit, cat_id
            )
            n_new += 1
        else:
            product_id = existing_id
            # Mise à jour image si on en a une et qu'il n'y en a pas
            if p.image_url:
                await conn.execute(
                    "UPDATE products SET image_url = COALESCE(image_url, $1), updated_at = NOW() WHERE id = $2",
                    p.image_url, product_id
                )
            n_updated += 1

        # Insérer le prix (toujours — historique)
        await conn.execute(
            """INSERT INTO prices (product_id, store_id, price, currency, is_promo, source, recorded_at)
               VALUES ($1, $2, $3, 'MAD', FALSE, 'scraper', NOW())""",
            product_id, store_id, p.price
        )

    return n_new, n_updated


async def _resolve_store_id(
    conn: asyncpg.Connection,
    scraper_slug: str,
    product_brand: str | None = None,
) -> int | None:
    """
    Résout le store_id pour un produit scrapé.
    Pour hmizate (agrégateur), tente de détecter l'enseigne depuis product.brand.
    """
    store_slug = SCRAPER_TO_STORE.get(scraper_slug)

    if store_slug is None and scraper_slug == "hmizate" and product_brand:
        # Détection de l'enseigne depuis le brand
        brand_lower = product_brand.lower().strip()
        for keyword, slug in HMIZATE_BRAND_TO_STORE.items():
            if keyword in brand_lower:
                store_slug = slug
                break

    if not store_slug:
        return None

    return await conn.fetchval(
        "SELECT id FROM stores WHERE slug = $1", store_slug
    )


async def persist_products_multi_store(
    conn: asyncpg.Connection,
    products: list[ScrapedProduct],
    scraper_slug: str,
    default_store_id: int | None,
) -> tuple[int, int]:
    """
    Variante de persist_products qui résout le store par produit (pour hmizate).
    """
    n_new = 0
    n_updated = 0

    for p in products:
        if not p.name or p.price <= 0:
            continue

        # Résolution du store
        store_id = default_store_id
        if scraper_slug == "hmizate":
            resolved = await _resolve_store_id(conn, scraper_slug, p.brand)
            if resolved:
                store_id = resolved

        if not store_id:
            continue   # impossible de rattacher à un magasin

        slug = slugify(p.name)
        cat_id = guess_category(p.name, p.category)

        existing_id = await conn.fetchval(
            "SELECT id FROM products WHERE slug = $1", slug
        )

        if existing_id is None:
            product_id = await conn.fetchval(
                """INSERT INTO products (name, slug, brand, image_url, unit, category_id, is_active)
                   VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                   RETURNING id""",
                p.name, slug, p.brand, p.image_url, p.unit, cat_id
            )
            n_new += 1
        else:
            product_id = existing_id
            if p.image_url:
                await conn.execute(
                    "UPDATE products SET image_url = COALESCE(image_url, $1), updated_at = NOW() WHERE id = $2",
                    p.image_url, product_id
                )
            n_updated += 1

        await conn.execute(
            """INSERT INTO prices (product_id, store_id, price, currency, is_promo, source, recorded_at)
               VALUES ($1, $2, $3, 'MAD', FALSE, 'scraper', NOW())""",
            product_id, store_id, p.price
        )

    return n_new, n_updated


async def run_scraper(scraper_slug: str, conn: asyncpg.Connection) -> None:
    store_slug = SCRAPER_TO_STORE.get(scraper_slug)

    # Pour hmizate : store_id optionnel (résolution par produit)
    store_id: int | None = None
    if store_slug:
        store_id = await conn.fetchval(
            "SELECT id FROM stores WHERE slug = $1", store_slug
        )
        if not store_id:
            logger.error(f"Store '{store_slug}' non trouvé en base")
            return
    elif scraper_slug not in SCRAPER_TO_STORE:
        logger.error(f"Scraper '{scraper_slug}' non trouvé dans SCRAPER_TO_STORE")
        return

    logger.info(f"\n{'='*60}")
    logger.info(f"Démarrage scraper: {scraper_slug} → store_id={store_id or 'multi-store'}")
    logger.info(f"{'='*60}")

    klass = SCRAPER_REGISTRY.get(scraper_slug)
    if not klass:
        logger.error(f"Scraper '{scraper_slug}' non trouvé dans le registry")
        return

    scraper = klass(rate_limit=2.0)
    run_log: list[str] = []

    try:
        result: ScrapeResult = await scraper.scrape(run_log=run_log)
        logger.info(
            f"[{scraper_slug}] Scraping terminé: {len(result.products)} produits, "
            f"{result.pages_scraped} pages, {result.captcha_hits} CAPTCHAs"
        )

        if result.errors:
            for err in result.errors[:5]:
                logger.warning(f"  Erreur: {err}")

        if result.products:
            if scraper_slug == "hmizate":
                n_new, n_updated = await persist_products_multi_store(
                    conn, result.products, scraper_slug, store_id
                )
            else:
                n_new, n_updated = await persist_products(conn, result.products, store_id)
            logger.info(f"[{scraper_slug}] Sauvegardé: {n_new} nouveaux, {n_updated} mis à jour")
        else:
            logger.warning(f"[{scraper_slug}] Aucun produit récupéré")

    except Exception as e:
        logger.error(f"[{scraper_slug}] Erreur fatale: {e}", exc_info=True)


async def main():
    targets = sys.argv[1:] if len(sys.argv) > 1 else ["all"]
    if "all" in targets:
        targets = [s for s in SCRAPER_TO_STORE.keys()]

    logger.info(f"Scrapers à exécuter: {targets}")
    logger.info("Connexion à la base de données...")

    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Stats avant
        count_before = await conn.fetchval("SELECT COUNT(*) FROM products")
        prices_before = await conn.fetchval("SELECT COUNT(*) FROM prices")
        logger.info(f"Avant scraping: {count_before} produits, {prices_before} prix")

        # Lancer les scrapers séquentiellement
        for slug in targets:
            if slug not in SCRAPER_TO_STORE and slug not in SCRAPER_REGISTRY:
                logger.warning(f"Scraper inconnu: {slug} (disponibles: {list(SCRAPER_TO_STORE.keys())})")
                continue
            await run_scraper(slug, conn)

        # Stats après
        count_after = await conn.fetchval("SELECT COUNT(*) FROM products")
        prices_after = await conn.fetchval("SELECT COUNT(*) FROM prices")
        logger.info(f"\n{'='*60}")
        logger.info(f"RÉSULTAT FINAL:")
        logger.info(f"  Produits: {count_before} → {count_after} (+{count_after - count_before})")
        logger.info(f"  Prix:     {prices_before} → {prices_after} (+{prices_after - prices_before})")
        logger.info(f"{'='*60}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
