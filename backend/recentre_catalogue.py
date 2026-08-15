"""
recentre_catalogue.py — Recentre le catalogue sur les consommables du foyer.

L'application porte sur les courses du ménage : nourriture, boissons, et
produits d'hygiène et d'entretien. Elle ne couvre ni l'électroménager, ni la
vaisselle et le rangement, ni la décoration ou le textile — présents dans les
catalogues d'enseignes mais hors sujet ici.

Les produits hors périmètre sont désactivés (is_active = false), jamais
supprimés : leurs prix et leur historique restent en base, et un simple
retour en arrière est possible.

L'appariement se fait sur des mots entiers. Sans cette précaution, « seMOULE »
serait classée en « moule à gâteau », et « PLAT cuisiné » en vaisselle.

Usage :
    DATABASE_URL="..." python recentre_catalogue.py [--appliquer] [--garder-hygiene]
"""
from __future__ import annotations

import asyncio
import re
import sys
import unicodedata
from collections import Counter

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Product

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

ELECTROMENAGER = (
    "televiseur", "tele", "tv", "machine a laver", "lave-linge", "lave linge",
    "refrigerateur", "frigo", "congelateur", "micro-ondes", "micro ondes",
    "friteuse", "air fryer", "airfryer", "aspirateur", "mixeur", "blender",
    "petrin", "cafetiere", "bouilloire", "grille-pain", "presse-agrumes",
    "extracteur", "centrifugeuse", "hachoir", "batteur", "plancha", "gaufrier",
    "crepiere", "rechaud", "hotte", "climatiseur", "ventilateur", "radiateur",
    "chauffage", "seche-cheveux", "tondeuse", "rasoir", "epilateur",
    "autocuiseur", "cuiseur", "samsung", "xiaomi", "iphone", "smartphone",
    "tablette", "ordinateur", "kingston", "casque", "ecouteur", "montre",
    "enceinte", "chargeur", "batterie externe", "imprimante",
    # Appareils désignés par « machine à … » : à distinguer du « détergent
    # machine », qui est bien un consommable.
    "machine a cafe", "machine espresso", "machine a panini", "machine a coudre",
    "machine a pain", "expresso", "capsules fakir", "gaufrier", "sorbetiere",
)

VAISSELLE_RANGEMENT = (
    "boite", "boites", "bol", "bols", "panier", "paniers", "corbeille", "seau",
    "bassine", "assiette", "assiettes", "verre", "verres", "tasse", "tasses",
    "mug", "couvert", "couverts", "couteau", "fourchette", "cuillere",
    "plateau", "saladier", "casserole", "casseroles", "poele", "marmite",
    "cocotte", "faitout", "theiere", "carafe", "pichet", "gourde",
    "organiseur", "chariot", "etagere", "rack", "cintre", "cintres",
    "louche", "spatule", "passoire", "rape", "moule", "bocal", "bocaux",
    "soupiere", "ramequin", "essoreuse", "planche a decouper", "tajine",
    "balai", "serpilliere", "raclette", "pelle",
)

DECO_TEXTILE = (
    "serviette", "serviettes", "drap", "draps", "couette", "oreiller",
    "coussin", "rideau", "rideaux", "tapis", "nappe", "pyjama", "chaussure",
    "chaussures", "vetement", "tee-shirt", "tshirt", "robe", "pantalon",
    "chemise", "chaussette", "peignoir", "bonnet", "echarpe", "cadre",
    "miroir", "vase", "bougie", "lampe", "guirlande", "decoration",
    "horloge", "tableau", "valise", "velo", "halteres", "jouet", "puzzle",
    "poupee", "trottinette", "ballon",
)

# Zone grise : consommables non alimentaires du quotidien.
HYGIENE_ENTRETIEN = (
    "shampooing", "shampoing", "savon", "gel douche", "dentifrice",
    "deodorant", "lessive", "detergent", "javel", "nettoyant", "desinfectant",
    "liquide vaisselle", "adoucissant", "papier toilette", "essuie-tout",
    "mouchoir", "couche", "couches", "lingette", "lingettes", "coton",
    "brosse a dents", "rasoir jetable", "serviette hygienique", "parfum",
    "creme", "lait corporel", "cologne", "insecticide", "desodorisant",
)


def sans_accents(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def contient_mot(texte: str, termes: tuple[str, ...]) -> bool:
    """Recherche sur mots entiers — « semoule » ne doit pas matcher « moule »."""
    for terme in termes:
        if re.search(rf"(?<![a-z]){re.escape(terme)}(?![a-z])", texte):
            return True
    return False


def categorie(nom: str) -> str:
    s = sans_accents(nom)
    if contient_mot(s, ELECTROMENAGER):
        return "electromenager"
    if contient_mot(s, HYGIENE_ENTRETIEN):
        return "hygiene"          # testé avant la vaisselle : « brosse à dents »
    if contient_mot(s, VAISSELLE_RANGEMENT):
        return "vaisselle"
    if contient_mot(s, DECO_TEXTILE):
        return "deco"
    return "alimentaire"


async def main() -> None:
    appliquer = "--appliquer" in sys.argv
    garder_hygiene = "--garder-hygiene" in sys.argv

    hors_perimetre = {"electromenager", "vaisselle", "deco"}
    if not garder_hygiene:
        hors_perimetre.add("hygiene")

    async with Session() as db:
        produits = (await db.execute(
            select(Product).where(Product.is_active.is_(True))
        )).scalars().all()

        compte = Counter()
        a_desactiver = []
        for p in produits:
            cat = categorie(p.name)
            compte[cat] += 1
            if cat in hors_perimetre:
                a_desactiver.append((p, cat))

        print(f"catalogue actif : {len(produits)} produits")
        for cat, n in compte.most_common():
            statut = "HORS PERIMETRE" if cat in hors_perimetre else "conserve"
            print(f"   {cat:16} {n:4}  {statut}")

        if appliquer:
            for p, _ in a_desactiver:
                p.is_active = False
            await db.commit()
            restant = len(produits) - len(a_desactiver)
            print(f"\n[APPLIQUE] {len(a_desactiver)} produits désactivés · "
                  f"{restant} produits conservés")
        else:
            print(f"\n[SIMULATION] {len(a_desactiver)} seraient désactivés · "
                  f"{len(produits) - len(a_desactiver)} conservés")
            print("\nÉchantillon des exclusions :")
            for p, cat in a_desactiver[:12]:
                print(f"   [{cat:14}] {p.name[:50]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
