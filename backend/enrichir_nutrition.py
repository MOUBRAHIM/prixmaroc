"""
enrichir_nutrition.py — Valeurs nutritionnelles pour tout le catalogue.

L'ancienne méthode appariait le nom du produit à une table de mots-clés
écrite à la main. Elle couvrait 16 % du catalogue : « Lait Alif » ne
correspondait à aucune entrée parce que la table connaissait « lait UHT ».

Claude lit le nom du produit et rend les valeurs pour 100 g, comme le ferait
quelqu'un consultant une table de composition. On ne lui demande rien qu'il
ne puisse savoir : ce sont des données publiques de référence, pas une mesure
propre à la marque.

Tout est vérifié avant écriture. Un modèle peut se tromper d'un facteur dix ;
la base ne doit pas en garder la trace.

Usage :
    python enrichir_nutrition.py [--tout] [--lots=N]
        --tout : recalcule aussi les produits déjà renseignés
"""
from __future__ import annotations

import asyncio
import json
import re
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import anthropic
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Product
from app.services.reponse_claude import texte_de

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

MODELE = "claude-haiku-4-5-20251001"
TAILLE_LOT = 25

# Bornes physiques pour 100 g. Au-delà, c'est une erreur, pas un aliment.
BORNES = {
    "calories": (0.0, 900.0),
    "proteines": (0.0, 100.0),
    "lipides": (0.0, 100.0),
    "glucides": (0.0, 100.0),
    "fibres": (0.0, 60.0),
}

CONSIGNE = """Tu donnes les valeurs nutritionnelles de produits alimentaires marocains,
pour 100 g ou 100 ml, d'après les tables de composition de référence.

Réponds UNIQUEMENT par un tableau JSON, un objet par produit, dans l'ordre reçu :
[{"i": 0, "calories": 364, "proteines": 10, "lipides": 1, "glucides": 76,
  "fibres": 2.7, "nutriscore": "B"}]

Règles :
- "i" reprend le numéro du produit dans la liste reçue.
- Les valeurs sont celles du produit tel qu'il se vend : une huile est à 100 g
  de lipides, une eau minérale à 0 partout.
- "nutriscore" vaut A, B, C, D, E, ou null si le produit n'en porte pas
  (eau, sel, épices, café, thé).
- Si le produit N'EST PAS alimentaire (lessive, savon, papier, couches),
  n'inclus pas d'objet pour lui : saute simplement son numéro.
- Si tu ne reconnais pas le produit, saute-le également. Une valeur inventée
  est pire qu'une absence.
- Les glucides incluent les sucres ; les fibres sont comptées à part."""


def _nombre(v: object, borne: tuple[float, float]) -> float | None:
    try:
        n = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return n if borne[0] <= n <= borne[1] else None


async def traiter_lot(claude, produits: list[Product]) -> int:
    liste = "\n".join(
        f"{i}. {p.name}" + (f" ({p.unit_size})" if p.unit_size else "")
        for i, p in enumerate(produits)
    )
    try:
        reponse = await claude.messages.create(
            model=MODELE, max_tokens=4096, system=CONSIGNE,
            messages=[{"role": "user", "content": liste}],
        )
    except Exception as e:
        print(f"    [erreur] {type(e).__name__}")
        return 0

    brut = re.sub(r"^```(?:json)?|```$", "", texte_de(reponse), flags=re.MULTILINE).strip()
    try:
        donnees = json.loads(brut)
    except json.JSONDecodeError:
        print("    [erreur] réponse illisible")
        return 0
    if not isinstance(donnees, list):
        return 0

    poses = 0
    for d in donnees:
        if not isinstance(d, dict):
            continue
        try:
            i = int(d.get("i"))
        except (TypeError, ValueError):
            continue
        if not 0 <= i < len(produits):
            continue

        kcal = _nombre(d.get("calories"), BORNES["calories"])
        if kcal is None:
            continue                      # sans énergie, la fiche n'a pas de sens

        p = produits[i]
        p.calories = kcal
        p.proteins = _nombre(d.get("proteines"), BORNES["proteines"])
        p.lipids = _nombre(d.get("lipides"), BORNES["lipides"])
        p.carbs = _nombre(d.get("glucides"), BORNES["glucides"])
        p.fibers = _nombre(d.get("fibres"), BORNES["fibres"])
        score = str(d.get("nutriscore") or "").strip().upper()
        p.nutriscore = score if score in ("A", "B", "C", "D", "E") else None
        poses += 1
    return poses


async def main() -> None:
    tout = "--tout" in sys.argv
    max_lots = next(
        (int(a.split("=")[1]) for a in sys.argv if a.startswith("--lots=")), 999
    )

    if not settings.ANTHROPIC_API_KEY:
        print("[STOP] ANTHROPIC_API_KEY absente.")
        return
    claude = anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY, max_retries=1, timeout=60.0
    )

    async with Session() as db:
        requete = select(Product).where(Product.is_active.is_(True))
        if not tout:
            requete = requete.where(Product.calories.is_(None))
        produits = list((await db.execute(requete.order_by(Product.id))).scalars())

        print(f"{len(produits)} produits à renseigner\n")
        total = 0
        for n in range(0, min(len(produits), max_lots * TAILLE_LOT), TAILLE_LOT):
            lot = produits[n:n + TAILLE_LOT]
            poses = await traiter_lot(claude, lot)
            await db.commit()
            total += poses
            print(f"  lot {n // TAILLE_LOT + 1:3} : {poses:2}/{len(lot)} renseignés")
            await asyncio.sleep(0.5)

        print(f"\n[TERMINÉ] {total} produits renseignés")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
