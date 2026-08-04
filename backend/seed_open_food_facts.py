#!/usr/bin/env python3
"""
Script de seed — Open Food Facts → PrixMaroc
Importe jusqu'à 5000 produits vendus au Maroc avec :
- Nom, marque, barcode, catégorie
- Infos nutritionnelles (calories, protéines, lipides, glucides, fibres, nutriscore)
- Photos téléchargées depuis OFF et uploadées sur Cloudflare R2

Usage :
    python seed_open_food_facts.py
    python seed_open_food_facts.py --limit 1000
    python seed_open_food_facts.py --limit 5000 --skip-existing
    python seed_open_food_facts.py --no-r2          # Garde les URLs OFF directes
    python seed_open_food_facts.py --update-existing
"""
import asyncio
import argparse
import hashlib
import io
import os
import re
import sys
import time
from typing import Optional

import httpx

sys.path.insert(0, os.path.dirname(__file__))

from sqlalchemy import select
from app.db import AsyncSessionLocal
from app.models.product import Product
from app.models.category import Category

# ─── Config Cloudflare R2 ─────────────────────────────────────────────────────

R2_ACCOUNT_ID     = os.getenv("R2_ACCOUNT_ID", "")
R2_ACCESS_KEY_ID  = os.getenv("R2_ACCESS_KEY_ID", "")
R2_SECRET_KEY     = os.getenv("R2_SECRET_ACCESS_KEY", "")
R2_BUCKET         = os.getenv("R2_BUCKET_NAME", "prixmaroc-images")
R2_PUBLIC_URL     = os.getenv("R2_PUBLIC_URL", "").rstrip("/")
R2_ENDPOINT       = f"https://{R2_ACCOUNT_ID}.r2.cloudflarestorage.com" if R2_ACCOUNT_ID else ""

# Dossier de destination dans le bucket
R2_PREFIX = "products"

# Taille max image téléchargée (5 Mo)
MAX_IMAGE_BYTES = 5 * 1024 * 1024

# Extensions acceptées
VALID_IMAGE_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp", "image/gif"}

# ─── Mapping catégories Open Food Facts → PrixMaroc ──────────────────────────

CATEGORY_MAP = {
    "en:cereals-and-their-products": "Céréales & Féculents",
    "en:cereals": "Céréales & Féculents",
    "en:breads": "Boulangerie",
    "en:pastries": "Boulangerie",
    "en:biscuits-and-cakes": "Biscuits & Gâteaux",
    "en:biscuits": "Biscuits & Gâteaux",
    "en:dairy-products": "Produits Laitiers",
    "en:milks": "Produits Laitiers",
    "en:yogurts": "Produits Laitiers",
    "en:cheeses": "Fromages",
    "en:meats": "Viandes",
    "en:poultry": "Volaille",
    "en:fish-and-seafood": "Poisson & Fruits de Mer",
    "en:fruits": "Fruits & Légumes",
    "en:vegetables": "Fruits & Légumes",
    "en:frozen-foods": "Surgelés",
    "en:beverages": "Boissons",
    "en:waters": "Eaux",
    "en:juices-and-nectars": "Jus de Fruits",
    "en:sodas": "Sodas",
    "en:plant-based-foods": "Végétal",
    "en:oils-and-fats": "Huiles & Corps Gras",
    "en:condiments": "Condiments & Sauces",
    "en:sauces": "Condiments & Sauces",
    "en:spices": "Épices & Condiments",
    "en:sugars": "Sucre & Confiseries",
    "en:chocolates": "Chocolat & Confiseries",
    "en:confectioneries": "Chocolat & Confiseries",
    "en:snacks": "Snacks & Apéritifs",
    "en:chips-and-fries": "Snacks & Apéritifs",
    "en:baby-foods": "Bébé",
    "en:coffee": "Café & Thé",
    "en:teas": "Café & Thé",
    "en:rice": "Riz & Pâtes",
    "en:pastas": "Riz & Pâtes",
    "en:legumes": "Légumineuses",
    "en:canned-foods": "Conserves",
    "en:jams": "Confitures & Miels",
    "en:honey": "Confitures & Miels",
    "en:cleaning-products": "Hygiène & Nettoyage",
    "en:hygiene-products": "Hygiène & Nettoyage",
}

DEFAULT_CATEGORY = "Épicerie"


# ─── Client R2 (boto3 synchrone dans thread pool) ────────────────────────────

def _make_r2_client():
    """Crée un client boto3 S3 pointant sur Cloudflare R2."""
    try:
        import boto3
        from botocore.config import Config
        return boto3.client(
            "s3",
            endpoint_url=R2_ENDPOINT,
            aws_access_key_id=R2_ACCESS_KEY_ID,
            aws_secret_access_key=R2_SECRET_KEY,
            config=Config(
                signature_version="s3v4",
                retries={"max_attempts": 3, "mode": "standard"},
            ),
            region_name="auto",
        )
    except Exception as e:
        print(f"  ⚠ Impossible de créer client R2: {e}")
        return None


def _r2_available() -> bool:
    """Vérifie que les variables R2 sont renseignées."""
    return bool(R2_ACCOUNT_ID and R2_ACCESS_KEY_ID and R2_SECRET_KEY and R2_PUBLIC_URL)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r'[àáâãäå]', 'a', text)
    text = re.sub(r'[èéêë]', 'e', text)
    text = re.sub(r'[ìíîï]', 'i', text)
    text = re.sub(r'[òóôõö]', 'o', text)
    text = re.sub(r'[ùúûü]', 'u', text)
    text = re.sub(r'[ç]', 'c', text)
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-')[:490]


def map_category(tags: list[str]) -> str:
    for tag in tags:
        if tag in CATEGORY_MAP:
            return CATEGORY_MAP[tag]
    for tag in tags:
        for key, val in CATEGORY_MAP.items():
            if key in tag:
                return val
    return DEFAULT_CATEGORY


def extract_nutriment(nutriments: dict, key: str) -> Optional[float]:
    val = nutriments.get(f"{key}_100g") or nutriments.get(key)
    if val is None:
        return None
    try:
        return round(float(val), 2)
    except (ValueError, TypeError):
        return None


def _content_type_to_ext(ct: str) -> str:
    """Retourne l'extension à partir du Content-Type."""
    mapping = {
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/webp": ".webp",
        "image/gif": ".gif",
    }
    return mapping.get(ct.split(";")[0].strip(), ".jpg")


def _r2_key_from_barcode(barcode: str, ext: str) -> str:
    """Génère la clé R2 depuis le barcode (répertoire barcode)."""
    return f"{R2_PREFIX}/{barcode}{ext}"


def _r2_key_from_hash(image_url: str, ext: str) -> str:
    """Génère la clé R2 depuis un hash de l'URL (fallback sans barcode)."""
    h = hashlib.md5(image_url.encode()).hexdigest()[:16]
    return f"{R2_PREFIX}/hash-{h}{ext}"


# ─── Upload photo vers R2 ─────────────────────────────────────────────────────

async def upload_photo_to_r2(
    http_client: httpx.AsyncClient,
    r2_client,
    image_url: str,
    barcode: Optional[str],
) -> Optional[str]:
    """
    Télécharge une photo depuis OFF et l'uploade sur Cloudflare R2.
    Retourne l'URL publique R2, ou None en cas d'échec.
    """
    if not image_url or not r2_client:
        return None

    # ── 1. Télécharger la photo ──────────────────────────────────────────────
    try:
        resp = await http_client.get(image_url, timeout=20, follow_redirects=True)
        if resp.status_code != 200:
            return None

        content_type = resp.headers.get("content-type", "image/jpeg").split(";")[0].strip()
        if content_type not in VALID_IMAGE_CONTENT_TYPES:
            return None

        image_bytes = resp.content
        if len(image_bytes) > MAX_IMAGE_BYTES:
            # Image trop grande → on garde l'URL OFF
            return None
        if len(image_bytes) < 500:
            # Trop petit (probablement une erreur)
            return None

    except Exception:
        return None

    # ── 2. Construire la clé R2 ───────────────────────────────────────────────
    ext = _content_type_to_ext(content_type)
    if barcode and barcode.isdigit():
        r2_key = _r2_key_from_barcode(barcode, ext)
    else:
        r2_key = _r2_key_from_hash(image_url, ext)

    # ── 3. Uploader en utilisant un thread (boto3 est synchrone) ─────────────
    try:
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: r2_client.put_object(
                Bucket=R2_BUCKET,
                Key=r2_key,
                Body=image_bytes,
                ContentType=content_type,
                # Cache longue durée — les photos produits ne changent pas souvent
                CacheControl="public, max-age=31536000",
            ),
        )
        return f"{R2_PUBLIC_URL}/{r2_key}"
    except Exception as e:
        # Quota / connexion : on tombe en fallback silencieux
        return None


# ─── Fetch Open Food Facts ────────────────────────────────────────────────────

async def fetch_page(client: httpx.AsyncClient, page: int, page_size: int = 100) -> list[dict]:
    url = "https://world.openfoodfacts.org/cgi/search.pl"
    params = {
        "action": "process",
        "tagtype_0": "countries",
        "tag_contains_0": "contains",
        "tag_0": "morocco",
        "json": 1,
        "page": page,
        "page_size": page_size,
        "fields": (
            "code,product_name,product_name_fr,brands,categories_tags,"
            "image_url,image_front_url,nutriments,nutriscore_grade,"
            "quantity,serving_size,packaging"
        ),
    }
    try:
        resp = await client.get(url, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("products", [])
    except Exception as e:
        print(f"  ⚠ Erreur page {page}: {e}")
        return []


# ─── Seed principal ───────────────────────────────────────────────────────────

async def seed(limit: int = 5000, skip_existing: bool = True, use_r2: bool = True):
    use_r2 = use_r2 and _r2_available()

    print(f"🚀 Démarrage seed Open Food Facts — cible: {limit} produits")
    print(f"   Source  : world.openfoodfacts.org (produits vendus au Maroc)")
    print(f"   Photos  : {'→ Cloudflare R2 (' + R2_BUCKET + ')' if use_r2 else '→ URL Open Food Facts (R2 désactivé)'}")
    if use_r2:
        print(f"   URL pub : {R2_PUBLIC_URL}/{R2_PREFIX}/")
    print()

    # Créer le client R2 une seule fois
    r2_client = _make_r2_client() if use_r2 else None
    if use_r2 and r2_client is None:
        print("  ⚠ Client R2 indisponible — fallback vers URLs OFF\n")
        use_r2 = False

    # Statistiques photos
    photos_uploaded = 0
    photos_fallback = 0
    photos_none     = 0

    async with AsyncSessionLocal() as db:
        category_cache: dict[str, int] = {}

        async def get_or_create_category(name: str) -> int:
            if name in category_cache:
                return category_cache[name]
            result = await db.execute(select(Category).where(Category.name == name))
            cat = result.scalar_one_or_none()
            if not cat:
                cat = Category(name=name, slug=slugify(name), icon="🛒")
                db.add(cat)
                await db.flush()
            category_cache[name] = cat.id
            return cat.id

        added    = 0
        updated  = 0
        skipped  = 0
        errors   = 0
        page     = 1
        page_size = 100

        # Client HTTP unique pour tout le script
        async with httpx.AsyncClient(
            headers={"User-Agent": "PrixMaroc/1.0 (contact@prixmaroc.ma)"},
            follow_redirects=True,
        ) as http_client:

            while added + updated < limit:
                products_raw = await fetch_page(http_client, page, page_size)
                if not products_raw:
                    print(f"  ℹ Page {page} vide — fin des résultats")
                    break

                print(f"  📦 Page {page}: {len(products_raw)} produits récupérés")

                for p in products_raw:
                    if added + updated >= limit:
                        break

                    try:
                        # ── Nom ──────────────────────────────────────────────
                        name = (
                            p.get("product_name_fr") or p.get("product_name") or ""
                        ).strip()
                        if not name or len(name) < 2:
                            skipped += 1
                            continue

                        barcode  = (p.get("code") or "").strip() or None
                        brand    = (p.get("brands") or "").split(",")[0].strip() or None
                        quantity = (p.get("quantity") or "").strip() or None

                        # ── URL photo originale (OFF CDN) ─────────────────────
                        off_image_url = (
                            p.get("image_front_url") or p.get("image_url") or None
                        )

                        # ── Catégorie ─────────────────────────────────────────
                        categories_tags = p.get("categories_tags", [])
                        category_name   = map_category(categories_tags)

                        # ── Nutriscore ────────────────────────────────────────
                        nutriscore = (p.get("nutriscore_grade") or "").upper() or None
                        if nutriscore and nutriscore not in ("A", "B", "C", "D", "E"):
                            nutriscore = None

                        # ── Nutriments ────────────────────────────────────────
                        nutriments = p.get("nutriments", {})
                        calories   = extract_nutriment(nutriments, "energy-kcal")
                        if calories is None:
                            kj = extract_nutriment(nutriments, "energy")
                            if kj:
                                calories = round(kj / 4.184, 1)
                        proteins = extract_nutriment(nutriments, "proteins")
                        lipids   = extract_nutriment(nutriments, "fat")
                        carbs    = extract_nutriment(nutriments, "carbohydrates")
                        fibers   = extract_nutriment(nutriments, "fiber")

                        # ── Slug ──────────────────────────────────────────────
                        base_slug = slugify(name)
                        if brand:
                            base_slug = slugify(f"{name}-{brand}")
                        if barcode:
                            base_slug = f"{base_slug}-{barcode[-4:]}"

                        category_id = await get_or_create_category(category_name)

                        # ── Doublon ? ─────────────────────────────────────────
                        existing = None
                        if barcode:
                            res = await db.execute(
                                select(Product).where(Product.barcode == barcode)
                            )
                            existing = res.scalar_one_or_none()

                        if existing is None:
                            res = await db.execute(
                                select(Product).where(Product.slug == base_slug)
                            )
                            existing = res.scalar_one_or_none()

                        if existing and skip_existing:
                            skipped += 1
                            continue

                        # ── Upload photo vers R2 ──────────────────────────────
                        final_image_url = off_image_url  # fallback par défaut

                        if off_image_url and use_r2:
                            r2_url = await upload_photo_to_r2(
                                http_client, r2_client, off_image_url, barcode
                            )
                            if r2_url:
                                final_image_url = r2_url
                                photos_uploaded += 1
                            else:
                                # R2 a échoué → on garde l'URL OFF
                                photos_fallback += 1
                        elif off_image_url:
                            photos_none += 1

                        # ── Créer ou mettre à jour ────────────────────────────
                        if existing:
                            existing.image_url  = final_image_url or existing.image_url
                            existing.calories   = calories  or existing.calories
                            existing.proteins   = proteins  or existing.proteins
                            existing.lipids     = lipids    or existing.lipids
                            existing.carbs      = carbs     or existing.carbs
                            existing.fibers     = fibers    or existing.fibers
                            existing.nutriscore = nutriscore or existing.nutriscore
                            updated += 1
                        else:
                            product = Product(
                                name=name,
                                slug=base_slug,
                                barcode=barcode,
                                brand=brand,
                                image_url=final_image_url,
                                unit_size=quantity,
                                category_id=category_id,
                                is_active=True,
                                calories=calories,
                                proteins=proteins,
                                lipids=lipids,
                                carbs=carbs,
                                fibers=fibers,
                                nutriscore=nutriscore,
                            )
                            db.add(product)
                            added += 1

                    except Exception as e:
                        errors += 1
                        if errors <= 10:
                            print(f"    ❌ Erreur produit: {e}")

                # ── Commit par page ───────────────────────────────────────────
                try:
                    await db.commit()
                    r2_info = f" (📸 {photos_uploaded} sur R2)" if use_r2 else ""
                    print(
                        f"     → {added} ajoutés, {updated} mis à jour, "
                        f"{skipped} ignorés{r2_info}"
                    )
                except Exception as e:
                    await db.rollback()
                    print(f"     ❌ Erreur commit: {e}")

                page += 1

                # Pause pour respecter les serveurs OFF
                await asyncio.sleep(0.5)

    # ── Résumé final ──────────────────────────────────────────────────────────
    print()
    print("=" * 55)
    print("✅ Seed terminé !")
    print(f"   📦 Produits ajoutés   : {added}")
    print(f"   🔄 Produits mis à jour: {updated}")
    print(f"   ⏭  Ignorés            : {skipped}")
    print(f"   ❌ Erreurs            : {errors}")
    print(f"   📊 Total traité       : {added + updated + skipped}")
    if use_r2:
        print()
        print(f"   📸 Photos sur R2      : {photos_uploaded}")
        print(f"   🔗 Fallback URL OFF   : {photos_fallback}")
        print(f"   ➖ Sans photo         : {photos_none}")
        pct = round(photos_uploaded / max(added + updated, 1) * 100)
        print(f"   🎯 Taux upload R2     : {pct}%")
    print("=" * 55)


# ─── Entrypoint ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed produits depuis Open Food Facts")
    parser.add_argument(
        "--limit", type=int, default=5000,
        help="Nombre max de produits (défaut: 5000)",
    )
    parser.add_argument(
        "--skip-existing", action="store_true", default=True,
        help="Ignorer les produits déjà en BDD",
    )
    parser.add_argument(
        "--update-existing", action="store_true",
        help="Mettre à jour les produits existants (remplace --skip-existing)",
    )
    parser.add_argument(
        "--no-r2", action="store_true",
        help="Désactiver l'upload R2 et garder les URLs Open Food Facts",
    )
    args = parser.parse_args()

    skip   = not args.update_existing
    use_r2 = not args.no_r2

    asyncio.run(seed(limit=args.limit, skip_existing=skip, use_r2=use_r2))
