"""
seed_prod.py — Seed production (Neon) via l'ORM.

Insère :
  • 6 catégories
  • 5 enseignes marocaines AVEC coordonnées GPS (pour la carte "magasins proches")
  • ~130 produits marocains réels (catalogue réutilisé depuis realistic_seed.py)
  • Prix par magasin + historique 6 mois

NE TOUCHE PAS à la table users (login préservé).

Usage :
  DATABASE_URL="postgresql://..." python seed_prod.py
"""
import asyncio
import sys
import random
import re

# psycopg async n'aime pas le ProactorEventLoop par défaut de Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
from datetime import datetime, timezone, timedelta
from decimal import Decimal

from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Store, Category, Product, Price
from app.models.price import PriceSource

# Réutilise le catalogue riche (adapté aux mots-clés de l'IA)
from realistic_seed import PRODUCTS, CATEGORY_MAP

engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ── Catégories (slug → nom, icône) — cohérent avec CATEGORY_MAP de realistic_seed
CATEGORIES = [
    ("epicerie",       "Épicerie",           "🛒"),
    ("produits-frais", "Produits frais",     "🥦"),
    ("boissons",       "Boissons",           "🧃"),
    ("hygiene-beaute", "Hygiène & Beauté",   "🧴"),
    ("entretien",      "Entretien maison",   "🧹"),
    ("bebe",           "Bébé",               "👶"),
]

# ── Enseignes avec GPS réels dans les grandes villes du Maroc + facteur de prix ──
# slug, nom, adresse, ville, région, lat, lng, facteur_prix
STORES = [
    # ── Casablanca-Settat ────────────────────────────────────────────────────
    ("marjane-californie",   "Marjane",        "Bd Panoramique, Californie",   "Casablanca",  "Casablanca-Settat",       33.5406, -7.6608, 1.00),
    ("labelvie-zerktouni",   "Label'Vie",      "Bd Zerktouni, Maârif",         "Casablanca",  "Casablanca-Settat",       33.5883, -7.6320, 1.03),
    ("bim-derbomar",         "BIM",            "Derb Omar",                    "Casablanca",  "Casablanca-Settat",       33.5928, -7.6192, 0.88),
    ("atacadao-eljadida",    "Atacadão",       "Route d'El Jadida",            "Casablanca",  "Casablanca-Settat",       33.5300, -7.6700, 0.93),
    ("acima-anfa",           "Acima",          "Bd d'Anfa",                    "Casablanca",  "Casablanca-Settat",       33.5920, -7.6350, 1.02),
    ("carrefour-morocco-mall","Carrefour",     "Morocco Mall, Ain Diab",       "Casablanca",  "Casablanca-Settat",       33.5741, -7.7050, 1.05),
    # ── Rabat-Salé-Kénitra ───────────────────────────────────────────────────
    ("carrefour-hayriad",    "Carrefour",      "Av. Annakhil, Hay Riad",       "Rabat",       "Rabat-Salé-Kénitra",      33.9548, -6.8676, 1.05),
    ("marjane-hayriad",      "Marjane",        "Hay Riad",                     "Rabat",       "Rabat-Salé-Kénitra",      33.9520, -6.8620, 1.00),
    ("aswak-assalam-kenitra","Aswak Assalam",  "Av. Mohammed V",               "Kénitra",     "Rabat-Salé-Kénitra",      34.2610, -6.5802, 0.98),
    ("bim-sale",             "BIM",            "Tabriquet",                    "Salé",        "Rabat-Salé-Kénitra",      34.0530, -6.7985, 0.88),
    # ── Marrakech-Safi ───────────────────────────────────────────────────────
    ("marjane-menara",       "Marjane",        "Av. Mohammed VI, Menara",      "Marrakech",   "Marrakech-Safi",          31.6295, -8.0142, 1.00),
    ("carrefour-marrakech",  "Carrefour",      "Carré Eden, Guéliz",           "Marrakech",   "Marrakech-Safi",          31.6360, -8.0080, 1.05),
    ("aswak-assalam-marrakech","Aswak Assalam","Route de Targa",               "Marrakech",   "Marrakech-Safi",          31.6420, -8.0350, 0.98),
    # ── Fès-Meknès ───────────────────────────────────────────────────────────
    ("marjane-fes",          "Marjane",        "Av. des FAR, Agdal",           "Fès",         "Fès-Meknès",              34.0331, -5.0003, 1.00),
    ("label-vie-fes",        "Label'Vie",      "Route d'Immouzer",             "Fès",         "Fès-Meknès",              34.0180, -4.9950, 1.03),
    ("marjane-meknes",       "Marjane",        "Av. des FAR",                  "Meknès",      "Fès-Meknès",              33.8935, -5.5473, 1.00),
    # ── Tanger-Tétouan-Al Hoceïma ────────────────────────────────────────────
    ("marjane-tanger",       "Marjane",        "Route de Rabat, Mghogha",      "Tanger",      "Tanger-Tétouan-Al Hoceïma", 35.7460, -5.8020, 1.00),
    ("carrefour-tanger",     "Carrefour",      "Ibn Battouta Mall",            "Tanger",      "Tanger-Tétouan-Al Hoceïma", 35.7380, -5.8330, 1.05),
    ("bim-tetouan",          "BIM",            "Av. Hassan II",                "Tétouan",     "Tanger-Tétouan-Al Hoceïma", 35.5720, -5.3720, 0.88),
    # ── Souss-Massa ──────────────────────────────────────────────────────────
    ("marjane-agadir",       "Marjane",        "Av. Hassan II, Founty",        "Agadir",      "Souss-Massa",             30.4110, -9.5730, 1.00),
    ("aswak-assalam-agadir", "Aswak Assalam",  "Av. Mohammed V",               "Agadir",      "Souss-Massa",             30.4230, -9.5980, 0.98),
    # ── Oriental ─────────────────────────────────────────────────────────────
    ("marjane-oujda",        "Marjane",        "Bd Mohammed VI",               "Oujda",       "Oriental",                34.6820, -1.9080, 1.00),
]


def slugify(text: str) -> str:
    text = text.lower().strip()
    for fr, en in [("à","a"),("â","a"),("ä","a"),("é","e"),("è","e"),("ê","e"),
                   ("ë","e"),("î","i"),("ï","i"),("ô","o"),("ö","o"),("ù","u"),
                   ("û","u"),("ü","u"),("ç","c"),("'","-"),("’","-")]:
        text = text.replace(fr, en)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:490]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # ── 1. Nettoyage (produits/prix uniquement, users préservés) ────────────
        print("Nettoyage prices/products…")
        await db.execute(delete(Price))
        await db.execute(delete(Product))
        await db.commit()

        # ── 2. Catégories (upsert par slug) ─────────────────────────────────────
        res = await db.execute(select(Category))
        existing_cats = {c.slug: c for c in res.scalars().all()}
        cat_id_by_slug: dict[str, int] = {}
        for slug, name, icon in CATEGORIES:
            if slug in existing_cats:
                cat_id_by_slug[slug] = existing_cats[slug].id
            else:
                c = Category(name=name, slug=slug, icon=icon)
                db.add(c)
                await db.flush()
                cat_id_by_slug[slug] = c.id
        # Map l'index numérique de CATEGORY_MAP (1..6) → id réel
        # CATEGORY_MAP: {"epicerie":1, "produits-frais":2, ...}
        slug_by_num = {v: k for k, v in CATEGORY_MAP.items()}

        # ── 3. Stores avec GPS (upsert par slug) ────────────────────────────────
        res = await db.execute(select(Store))
        existing_stores = {s.slug: s for s in res.scalars().all()}
        store_rows: list[tuple[Store, float]] = []
        for slug, name, address, city, region, lat, lng, factor in STORES:
            s = existing_stores.get(slug)
            if s is None:
                s = Store(slug=slug, name=name, address=address, city=city,
                          region=region, latitude=lat, longitude=lng, is_active=True)
                db.add(s)
            else:
                s.name, s.address, s.city = name, address, city
                s.region, s.latitude, s.longitude, s.is_active = region, lat, lng, True
            await db.flush()
            store_rows.append((s, factor))

        # ── 4. Produits + prix ──────────────────────────────────────────────────
        n_prod = n_price = 0
        now = datetime.now(timezone.utc)
        for (name, brand, cat_slug, img_key, unit, ref_price, _key) in PRODUCTS:
            # cat_slug dans realistic_seed est déjà un slug (ex "epicerie")
            cid = cat_id_by_slug.get(cat_slug)
            if cid is None:
                # tolère un slug numérique éventuel
                cid = cat_id_by_slug.get(slug_by_num.get(cat_slug, ""), None)
            prod = Product(
                name=name, slug=slugify(name), brand=brand,
                image_url=f"https://images.prixmaroc.ma/products/{img_key}.jpg",
                unit=unit, category_id=cid, is_active=True,
            )
            db.add(prod)
            await db.flush()
            n_prod += 1

            for store, factor in store_rows:
                base = round(ref_price * factor, 2)
                cur = round(base * random.uniform(0.96, 1.04) * 2) / 2
                is_promo = random.random() < 0.20
                promo = round(cur * random.uniform(0.80, 0.92), 2) if is_promo else None
                db.add(Price(
                    product_id=prod.id, store_id=store.id, price=Decimal(str(cur)),
                    currency="MAD", is_promo=is_promo,
                    promo_price=Decimal(str(promo)) if promo else None,
                    source=PriceSource.SCRAPER, recorded_at=now,
                ))
                n_price += 1
                # Historique 6 mois
                for m in [6, 5, 4, 3, 2, 1]:
                    infl = 1 + (m * 0.004)
                    hp = round(cur / infl * random.uniform(0.97, 1.03) * 2) / 2
                    db.add(Price(
                        product_id=prod.id, store_id=store.id, price=Decimal(str(hp)),
                        currency="MAD", is_promo=False, source=PriceSource.SCRAPER,
                        recorded_at=now - timedelta(days=m * 30),
                    ))
                    n_price += 1

        await db.commit()
        print(f"[OK] Seed prod termine : {len(CATEGORIES)} categories, "
              f"{len(STORES)} magasins (GPS), {n_prod} produits, {n_price} prix.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
