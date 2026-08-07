"""
enrich_products.py — Complète le catalogue produits.

1. Valeurs nutritionnelles (pour 100 g / 100 ml) issues des tables de
   composition de référence (CIQUAL / USDA). Appariement par mots-clés sur
   le nom du produit.
2. Nettoie les URLs d'images mortes (le domaine images.prixmaroc.ma n'existe
   pas) : on met image_url à NULL et l'application affiche une vignette
   illustrée par catégorie — plus fiable et sans problème de droits.

Usage :
    DATABASE_URL="postgresql://..." python enrich_products.py
"""
from __future__ import annotations

import asyncio
import os
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Product

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# (kcal, protéines, lipides, glucides, fibres, nutriscore)  pour 100 g / 100 ml
N = tuple[float, float, float, float, float, str | None]

# Parcouru dans l'ordre : le premier mot-clé contenu dans le nom gagne.
# Les libellés les plus spécifiques viennent avant les plus génériques.
NUTRITION: list[tuple[str, N]] = [
    # ── Huiles & corps gras ────────────────────────────────────────────────
    ("huile d'olive",      (900, 0.0, 100.0, 0.0, 0.0, "D")),
    ("huile de tournesol", (900, 0.0, 100.0, 0.0, 0.0, "D")),
    ("huile de soja",      (900, 0.0, 100.0, 0.0, 0.0, "D")),
    ("beurre",             (717, 0.9, 81.0, 0.1, 0.0, "E")),
    ("margarine",          (700, 0.2, 80.0, 0.7, 0.0, "D")),
    ("crème fraîche",      (292, 2.1, 30.0, 2.9, 0.0, "D")),

    # ── Sucre, miel, confitures ────────────────────────────────────────────
    ("sucre",              (400, 0.0, 0.0, 100.0, 0.0, "E")),
    ("miel",               (304, 0.3, 0.0, 82.0, 0.2, "D")),
    ("confiture",          (250, 0.4, 0.1, 60.0, 1.0, "D")),
    ("amlou",              (600, 15.0, 45.0, 30.0, 8.0, "C")),

    # ── Céréales, farines, pain ────────────────────────────────────────────
    ("farine complète",    (340, 13.0, 2.5, 72.0, 10.7, "A")),
    ("farine",             (364, 10.0, 1.0, 76.0, 2.7, "B")),
    ("levure",             (325, 40.0, 7.0, 40.0, 27.0, "A")),
    ("couscous",           (376, 12.8, 0.6, 77.0, 5.0, "A")),
    ("riz basmati",        (360, 7.5, 0.6, 79.0, 1.3, "A")),
    ("riz",                (360, 7.0, 0.6, 79.0, 1.3, "A")),
    ("spaghetti",          (371, 13.0, 1.5, 75.0, 3.2, "A")),
    ("penne",              (371, 13.0, 1.5, 75.0, 3.2, "A")),
    ("vermicelles",        (371, 13.0, 1.5, 75.0, 3.2, "A")),
    ("pain de mie complet",(240, 9.0, 3.5, 42.0, 6.0, "A")),
    ("pain de mie",        (265, 8.0, 3.5, 49.0, 2.5, "B")),
    ("biscottes",          (390, 12.0, 6.0, 72.0, 4.0, "B")),

    # ── Légumineuses ───────────────────────────────────────────────────────
    ("pois chiches",       (364, 19.0, 6.0, 61.0, 17.0, "A")),
    ("lentilles",          (352, 25.0, 1.1, 63.0, 10.7, "A")),
    ("haricots blancs",    (333, 23.0, 0.8, 60.0, 15.0, "A")),
    ("fèves",              (341, 26.0, 1.5, 58.0, 25.0, "A")),

    # ── Produits laitiers & œufs ───────────────────────────────────────────
    ("lait 1er âge",       (500, 10.0, 26.0, 57.0, 0.0, None)),
    ("lait uht demi",      (47, 3.3, 1.6, 4.8, 0.0, "B")),
    ("lait uht",           (61, 3.2, 3.3, 4.8, 0.0, "B")),
    ("yaourt",             (61, 3.5, 3.3, 4.7, 0.0, "B")),
    ("fromage blanc",      (90, 8.0, 3.0, 4.0, 0.0, "B")),
    ("fromage fondu",      (300, 10.0, 25.0, 6.0, 0.0, "D")),
    ("fromage raibi",      (75, 3.2, 2.5, 10.0, 0.0, "C")),
    ("œufs",               (143, 12.6, 9.5, 0.7, 0.0, "A")),
    ("oeufs",              (143, 12.6, 9.5, 0.7, 0.0, "A")),

    # ── Viandes (halal) ────────────────────────────────────────────────────
    ("blancs de poulet",   (165, 31.0, 3.6, 0.0, 0.0, "A")),
    ("cuisses de poulet",  (185, 25.0, 9.0, 0.0, 0.0, "B")),
    ("foie de poulet",     (119, 17.0, 4.8, 0.7, 0.0, "A")),
    ("poulet entier",      (165, 31.0, 3.6, 0.0, 0.0, "A")),
    ("dinde",              (150, 27.0, 4.0, 0.0, 0.0, "A")),
    ("viande hachée",      (250, 26.0, 15.0, 0.0, 0.0, "C")),
    ("kefta",              (250, 25.0, 16.0, 1.0, 0.0, "C")),
    ("merguez",            (300, 17.0, 25.0, 1.5, 0.0, "D")),
    ("agneau",             (294, 25.0, 21.0, 0.0, 0.0, "D")),
    ("escalope de veau",   (172, 24.0, 8.0, 0.0, 0.0, "B")),

    # ── Poissons & fruits de mer ───────────────────────────────────────────
    ("sardines fraîches",  (208, 25.0, 11.0, 0.0, 0.0, "A")),
    ("sardines",           (217, 24.0, 13.0, 0.0, 0.0, "B")),
    ("thon",               (116, 26.0, 1.0, 0.0, 0.0, "A")),
    ("sole",               (86, 18.0, 1.2, 0.0, 0.0, "A")),
    ("crevettes",          (99, 24.0, 0.3, 0.2, 0.0, "A")),

    # ── Légumes frais ──────────────────────────────────────────────────────
    ("tomates pelées",     (20, 1.0, 0.2, 3.5, 1.2, "A")),
    ("tomates",            (18, 0.9, 0.2, 3.9, 1.2, "A")),
    ("oignons",            (40, 1.1, 0.1, 9.3, 1.7, "A")),
    ("pommes de terre",    (77, 2.0, 0.1, 17.0, 2.2, "A")),
    ("carottes",           (41, 0.9, 0.2, 9.6, 2.8, "A")),
    ("courgettes",         (17, 1.2, 0.3, 3.1, 1.0, "A")),
    ("poivrons",           (31, 1.0, 0.3, 6.0, 2.1, "A")),
    ("aubergines",         (25, 1.0, 0.2, 5.9, 3.0, "A")),
    ("navets",             (28, 0.9, 0.1, 6.4, 1.8, "A")),
    ("chou blanc",         (25, 1.3, 0.1, 5.8, 2.5, "A")),
    ("epinards",           (23, 2.9, 0.4, 3.6, 2.2, "A")),
    ("épinards",           (23, 2.9, 0.4, 3.6, 2.2, "A")),
    ("haricots verts",     (31, 1.8, 0.1, 7.0, 3.4, "A")),
    ("betteraves",         (43, 1.6, 0.2, 9.6, 2.8, "A")),
    ("petits pois",        (81, 5.4, 0.4, 14.0, 5.7, "A")),
    ("ail",                (149, 6.4, 0.5, 33.0, 2.1, "A")),
    ("persil",             (36, 3.0, 0.8, 6.3, 3.3, "A")),

    # ── Fruits ─────────────────────────────────────────────────────────────
    ("oranges",            (47, 0.9, 0.1, 11.8, 2.4, "A")),
    ("pommes 1kg",         (52, 0.3, 0.2, 14.0, 2.4, "A")),
    ("bananes",            (89, 1.1, 0.3, 23.0, 2.6, "A")),
    ("clémentines",        (47, 0.9, 0.2, 12.0, 1.7, "A")),
    ("grenades",           (83, 1.7, 1.2, 19.0, 4.0, "A")),
    ("raisins",            (69, 0.7, 0.2, 18.0, 0.9, "A")),
    ("pastèque",           (30, 0.6, 0.2, 7.6, 0.4, "A")),
    ("dattes",             (277, 1.8, 0.2, 75.0, 6.7, "C")),
    ("figues",             (249, 3.3, 0.9, 64.0, 9.8, "B")),

    # ── Boissons ───────────────────────────────────────────────────────────
    ("eau minérale",       (0, 0.0, 0.0, 0.0, 0.0, "A")),
    ("coca-cola",          (42, 0.0, 0.0, 10.6, 0.0, "E")),
    ("pepsi",              (42, 0.0, 0.0, 10.6, 0.0, "E")),
    ("ice tea",            (30, 0.0, 0.0, 7.5, 0.0, "D")),
    ("jus d'orange",       (45, 0.7, 0.2, 10.4, 0.2, "C")),
    ("jus de raisin",      (60, 0.4, 0.1, 15.0, 0.2, "C")),

    # ── Épicerie salée / condiments ────────────────────────────────────────
    ("double concentré",   (82, 4.3, 0.5, 15.0, 3.5, "A")),
    ("harissa",            (100, 3.0, 5.0, 10.0, 5.0, "B")),
    ("olives",             (145, 1.0, 15.0, 3.8, 3.3, "C")),
    ("citrons confits",    (30, 1.0, 0.3, 5.0, 3.0, "B")),
    ("sel fin",            (0, 0.0, 0.0, 0.0, 0.0, None)),

    # ── Épices (consommées en très petites quantités) ──────────────────────
    ("cumin",              (375, 18.0, 22.0, 44.0, 11.0, None)),
    ("paprika",            (282, 14.0, 13.0, 54.0, 35.0, None)),
    ("ras el hanout",      (330, 12.0, 15.0, 50.0, 25.0, None)),
    ("gingembre",          (335, 9.0, 4.2, 72.0, 14.0, None)),
    ("curcuma",            (354, 8.0, 10.0, 65.0, 21.0, None)),
    ("cannelle",           (247, 4.0, 1.2, 81.0, 53.0, None)),
    ("safran",             (310, 11.4, 5.9, 65.0, 3.9, None)),
    ("poivre noir",        (251, 10.4, 3.3, 64.0, 25.0, None)),

    # ── Café & thé (poudre / feuilles sèches) ──────────────────────────────
    ("café soluble",       (353, 12.0, 0.5, 41.0, 0.0, None)),
    ("café",               (200, 11.0, 13.0, 40.0, 20.0, None)),
    ("thé",                (1, 0.0, 0.0, 0.3, 0.0, None)),
]

# Produits non alimentaires : aucune valeur nutritionnelle
NON_FOOD = (
    "dentifrice", "shampooing", "savon", "gel douche", "déodorant",
    "lessive", "javel", "liquide vaisselle", "nettoyant", "papier toilette",
    "couches", "lingettes",
)


def match(name: str) -> N | None:
    n = name.lower()
    if any(k in n for k in NON_FOOD):
        return None
    for keyword, values in NUTRITION:
        if keyword in n:
            return values
    return None


async def main() -> None:
    async with Session() as db:
        products = (await db.execute(select(Product))).scalars().all()
        enriched = cleaned = skipped = 0

        for i, p in enumerate(products, 1):
            # Commit régulier : Neon (serverless) coupe les transactions longues
            if i % 20 == 0:
                await db.commit()
            # 1. URLs d'images mortes → NULL (vignette illustrée côté app)
            if p.image_url and "images.prixmaroc.ma" in p.image_url:
                p.image_url = None
                cleaned += 1

            # 2. Valeurs nutritionnelles
            values = match(p.name)
            if values is None:
                skipped += 1
                continue
            kcal, prot, lip, carb, fib, score = values
            p.calories, p.proteins, p.lipids = kcal, prot, lip
            p.carbs, p.fibers, p.nutriscore = carb, fib, score
            enriched += 1

        await db.commit()
        print(f"[OK] {enriched} produits enrichis | {cleaned} images mortes nettoyees "
              f"| {skipped} sans valeurs (non alimentaires)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
