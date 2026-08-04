#!/usr/bin/env python3
"""
seed_prices.py — PrixMaroc
Seed realistic prices for products that currently have fewer than 3 price records.
Usage (inside the backend container or with PYTHONPATH set):
    python scripts/seed_prices.py
"""
import asyncio
import sys
import random

sys.path.insert(0, '/app')

from app.db import AsyncSessionLocal
from app.models.product import Product
from app.models.store import Store
from app.models.price import Price, PriceSource
from sqlalchemy import select, func


# ─── Price estimation based on product name ───────────────────────────────────

def estimate_base_price(name: str) -> float:
    name_lower = name.lower()
    if any(k in name_lower for k in ['huile', 'oil']):
        return random.uniform(35, 120)
    if any(k in name_lower for k in ['lait', 'milk']):
        return random.uniform(7, 18)
    if any(k in name_lower for k in ['eau', 'water', 'sidi', 'oulmes']):
        return random.uniform(3, 8)
    if any(k in name_lower for k in ['yaourt', 'yogurt', 'danone']):
        return random.uniform(4, 12)
    if any(k in name_lower for k in ['pain', 'bread', 'biscuit']):
        return random.uniform(5, 25)
    if any(k in name_lower for k in ['sucre', 'farine', 'sel']):
        return random.uniform(6, 45)
    if any(k in name_lower for k in ['savon', 'shampooing', 'dentifrice']):
        return random.uniform(15, 65)
    if any(k in name_lower for k in ['lessive', 'tide', 'omo']):
        return random.uniform(45, 160)
    if any(k in name_lower for k in ['thé', 'tea', 'café', 'coffee']):
        return random.uniform(18, 80)
    if any(k in name_lower for k in ['chocolat', 'biscuit', 'chips', 'snack']):
        return random.uniform(10, 55)
    return random.uniform(12, 85)


# ─── Per-chain price multipliers ─────────────────────────────────────────────

CHAIN_MULT: dict[str, float] = {
    'marjane':   1.00,
    'carrefour': 1.02,
    'labelvie':  1.05,
    'bim':       0.88,
    'atacadao':  0.92,
    'kazyon':    0.85,
    'aswak':     1.08,
    'acima':     1.03,
}


# ─── Main ─────────────────────────────────────────────────────────────────────

async def main() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Find products with fewer than 3 price entries
        result = await db.execute(
            select(Product.id, Product.name, func.count(Price.id).label('nb'))
            .outerjoin(Price, Price.product_id == Product.id)
            .group_by(Product.id, Product.name)
            .having(func.count(Price.id) < 3)
        )
        products_few = result.all()
        print(f"Products needing prices: {len(products_few)}")

        if not products_few:
            print("Nothing to seed — all products already have >= 3 prices.")
            return

        # 2. Load all stores
        stores_result = await db.execute(select(Store.id, Store.slug))
        all_stores = [(row[0], row[1]) for row in stores_result]

        if not all_stores:
            print("No stores found — run the main seed script first.")
            return

        # 3. Group store IDs by chain slug
        chain_stores: dict[str, list[int]] = {}
        for store_id, store_slug in all_stores:
            for chain in CHAIN_MULT:
                if chain in store_slug.lower():
                    chain_stores.setdefault(chain, []).append(store_id)

        # 4. Seed one price per chain per under-priced product
        prices_added = 0

        for prod_id, prod_name, _ in products_few:
            base = estimate_base_price(prod_name)

            for chain, mult in CHAIN_MULT.items():
                stores = chain_stores.get(chain, [])
                if not stores:
                    continue

                store_id = random.choice(stores)
                noise = random.uniform(-0.08, 0.08)
                price_val = round(base * mult * (1 + noise), 2)

                # ~18% chance of being on promotion
                is_promo = random.random() < 0.18

                p = Price(
                    product_id=prod_id,
                    store_id=store_id,
                    # When promo: store the "before" price inflated by ~17.6 %
                    price=round(price_val * (1 / 0.85), 2) if is_promo else price_val,
                    promo_price=price_val if is_promo else None,
                    is_promo=is_promo,
                    source=PriceSource.MANUAL,
                )
                db.add(p)
                prices_added += 1

        await db.commit()
        print(f"✓ {prices_added} prix ajoutés")


if __name__ == '__main__':
    asyncio.run(main())
