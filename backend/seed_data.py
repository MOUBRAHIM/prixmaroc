"""
Script de seed — PrixMaroc
Insère des magasins, catégories, produits et prix de test dans la base.
Lancer avec : docker exec -i prixmaroc-backend-1 python /app/seed_data.py
"""
import asyncio
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import random

from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Base, Store, Category, Product, Price
from app.models.price import PriceSource

DATABASE_URL = settings.DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# ── Données ───────────────────────────────────────────────────────────────────

STORES = [
    {"name": "Marjane", "slug": "marjane-casa", "address": "Bd Mohammed V", "city": "Casablanca", "region": "Grand Casablanca"},
    {"name": "Carrefour", "slug": "carrefour-rabat", "address": "Av. Annakhil, Hay Riad", "city": "Rabat", "region": "Rabat-Salé-Kénitra"},
    {"name": "Label'Vie", "slug": "labelvie-casa", "address": "Bd Zerktouni", "city": "Casablanca", "region": "Grand Casablanca"},
    {"name": "BIM", "slug": "bim-casa", "address": "Derb Omar", "city": "Casablanca", "region": "Grand Casablanca"},
    {"name": "Atacadão", "slug": "atacadao-casa", "address": "Route d'El Jadida", "city": "Casablanca", "region": "Grand Casablanca"},
]

CATEGORIES = [
    {"name": "Épicerie", "slug": "epicerie", "icon": "🛒"},
    {"name": "Produits laitiers", "slug": "laitiers", "icon": "🥛"},
    {"name": "Viandes & Volailles", "slug": "viandes", "icon": "🥩"},
    {"name": "Fruits & Légumes", "slug": "fruits-legumes", "icon": "🥦"},
    {"name": "Boissons", "slug": "boissons", "icon": "🧃"},
    {"name": "Hygiène", "slug": "hygiene", "icon": "🧴"},
    {"name": "Nettoyage", "slug": "nettoyage", "icon": "🧹"},
    {"name": "Boulangerie", "slug": "boulangerie", "icon": "🍞"},
]

# (name, brand, unit_size, category_slug, base_price_mad)
PRODUCTS = [
    # Épicerie
    ("Huile de table Lesieur", "Lesieur", "2L", "epicerie", 38.0),
    ("Huile d'olive Olivia", "Olivia", "1L", "epicerie", 75.0),
    ("Sucre raffiné Cosumar", "Cosumar", "2kg", "epicerie", 18.0),
    ("Farine Zitoun", "Zitoun", "5kg", "epicerie", 42.0),
    ("Riz long grain", "Tilda", "5kg", "epicerie", 55.0),
    ("Pâtes Randa spaghetti", "Randa", "500g", "epicerie", 6.5),
    ("Lentilles vertes", None, "1kg", "epicerie", 14.0),
    ("Pois chiches", None, "1kg", "epicerie", 12.0),
    ("Sel de table", "Saltis", "1kg", "epicerie", 3.5),
    ("Tomates pelées en boîte", "Aïcha", "400g", "epicerie", 8.5),
    ("Concentré de tomate Aïcha", "Aïcha", "135g", "epicerie", 5.5),
    ("Harissa Aïcha", "Aïcha", "380g", "epicerie", 12.0),
    ("Sardines à l'huile", "Doha", "125g", "epicerie", 9.0),
    ("Thon en boîte", "Nador", "160g", "epicerie", 15.5),
    ("Bissara (fèves)", None, "1kg", "epicerie", 11.0),
    # Produits laitiers
    ("Lait Centrale demi-écrémé", "Centrale", "1L", "laitiers", 7.5),
    ("Yaourt nature Jaouda", "Jaouda", "4x125g", "laitiers", 12.0),
    ("Fromage fondu Vache qui rit", "Bel", "8 portions", "laitiers", 19.5),
    ("Beurre doux Bridel", "Bridel", "250g", "laitiers", 28.0),
    ("Crème fraîche Délice", "Délice", "200ml", "laitiers", 11.5),
    ("Lait condensé Gloria", "Nestlé", "397g", "laitiers", 15.0),
    # Viandes
    ("Poulet fermier entier", None, "1kg", "viandes", 32.0),
    ("Kefta bœuf", None, "500g", "viandes", 45.0),
    ("Merguez agneau", None, "500g", "viandes", 52.0),
    # Fruits & Légumes
    ("Tomates rondes", None, "1kg", "fruits-legumes", 5.0),
    ("Pommes de terre", None, "1kg", "fruits-legumes", 4.5),
    ("Oignons", None, "1kg", "fruits-legumes", 3.5),
    ("Carottes", None, "1kg", "fruits-legumes", 4.0),
    ("Courgettes", None, "1kg", "fruits-legumes", 6.0),
    ("Citrons", None, "1kg", "fruits-legumes", 7.0),
    ("Bananes", None, "1kg", "fruits-legumes", 9.5),
    ("Pommes Golden", None, "1kg", "fruits-legumes", 12.0),
    ("Oranges Maroc", None, "1kg", "fruits-legumes", 6.5),
    # Boissons
    ("Eau minérale Sidi Ali", "Sidi Ali", "1.5L", "boissons", 4.5),
    ("Eau minérale Ain Saïss", "Ain Saïss", "1.5L", "boissons", 3.5),
    ("Jus d'orange Pago", "Pago", "1L", "boissons", 22.0),
    ("Coca-Cola", "Coca-Cola", "2L", "boissons", 18.0),
    ("Café Najjar moulu", "Najjar", "200g", "boissons", 28.0),
    ("Thé Lipton jaune", "Lipton", "100 sachets", "boissons", 24.0),
    ("Thé Atay marocain", "Ringtea", "200g", "boissons", 18.0),
    # Hygiène
    ("Dentifrice Colgate", "Colgate", "75ml", "hygiene", 14.5),
    ("Shampoing Head & Shoulders", "P&G", "400ml", "hygiene", 38.0),
    ("Savon Palmolive", "Palmolive", "3x90g", "hygiene", 16.0),
    ("Gel douche Dove", "Dove", "250ml", "hygiene", 32.0),
    ("Déodorant Rexona", "Rexona", "150ml", "hygiene", 28.0),
    # Nettoyage
    ("Lessive Tide en poudre", "Tide", "5kg", "nettoyage", 72.0),
    ("Liquide vaisselle Axion", "Axion", "750ml", "nettoyage", 14.0),
    ("Javel Cif", "Cif", "1L", "nettoyage", 11.0),
    # Boulangerie
    ("Pain de mie Amor", "Amor", "500g", "boulangerie", 11.5),
    ("Msemen surgelé", None, "10 pièces", "boulangerie", 22.0),
    ("Biscuits Digestive", "McVities", "400g", "boulangerie", 35.0),
]


async def seed():
    async with AsyncSessionLocal() as db:
        # ── Catégories ────────────────────────────────────────────────────────
        print("Insertion des catégories...")
        cat_map = {}
        for c in CATEGORIES:
            cat = Category(name=c["name"], slug=c["slug"], icon=c["icon"])
            db.add(cat)
        await db.flush()

        # Re-fetch categories to get IDs
        from sqlalchemy import select
        result = await db.execute(select(Category))
        for cat in result.scalars():
            cat_map[cat.slug] = cat.id

        # ── Magasins ──────────────────────────────────────────────────────────
        print("Insertion des magasins...")
        store_objs = []
        for s in STORES:
            store = Store(
                name=s["name"],
                slug=s["slug"],
                address=s["address"],
                city=s["city"],
                region=s["region"],
                is_active=True,
            )
            db.add(store)
            store_objs.append(store)
        await db.flush()

        result = await db.execute(select(Store))
        stores = result.scalars().all()

        # ── Produits & Prix ───────────────────────────────────────────────────
        print(f"Insertion de {len(PRODUCTS)} produits et de leurs prix...")
        for name, brand, unit_size, cat_slug, base_price in PRODUCTS:
            slug = name.lower().replace(" ", "-").replace("'", "").replace("&", "")[:80]
            product = Product(
                name=name,
                slug=slug,
                brand=brand,
                unit_size=unit_size,
                category_id=cat_map.get(cat_slug),
                is_active=True,
            )
            db.add(product)
            await db.flush()

            # Prix dans chaque magasin avec variation ±15%
            for store in stores:
                variation = random.uniform(-0.12, 0.15)
                price_val = round(base_price * (1 + variation), 2)

                # 20% de chance d'avoir une promo
                is_promo = random.random() < 0.20
                promo_price = round(price_val * random.uniform(0.75, 0.90), 2) if is_promo else None
                promo_end = datetime.now(timezone.utc) + timedelta(days=random.randint(3, 14)) if is_promo else None

                # Quelques relevés historiques (30 jours)
                for days_ago in [0, 7, 14, 21, 30]:
                    hist_price = round(price_val * random.uniform(0.95, 1.08), 2)
                    price_obj = Price(
                        product_id=product.id,
                        store_id=store.id,
                        price=Decimal(str(hist_price)),
                        currency="MAD",
                        is_promo=is_promo and days_ago == 0,
                        promo_price=Decimal(str(promo_price)) if (is_promo and days_ago == 0) else None,
                        promo_end=promo_end if (is_promo and days_ago == 0) else None,
                        source=PriceSource.MANUAL,
                        recorded_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
                    )
                    db.add(price_obj)

        await db.commit()
        print(f"✅ Seed terminé : {len(CATEGORIES)} catégories, {len(STORES)} magasins, {len(PRODUCTS)} produits")


if __name__ == "__main__":
    asyncio.run(seed())
