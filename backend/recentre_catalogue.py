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
    "apple watch", "smartwatch", "plaque gaz", "plaque de cuisson", "barbecue",
    "trancheuse", "yaourtiere", "deshydrateur", "purificateur", "humidificateur",
    # « four » seul écarterait les « petits fours », qui sont des biscuits.
    "mini four", "four electrique", "plaque chauffante", "moulin a cafe",
    "brosse a dents electrique", "robot menager", "table de cuisson",
    "chauffe-eau", "chauffe eau", "climatiseur", "ventilateur",
    "oppo", "realme", "infinix", "tecno", "huawei", "cable", "usb", "adaptateur",
    "power bank", "clavier", "souris", "manette",
)

# Restes d'extraction : mentions de mise en page prises pour des produits.
FRAGMENTS = (
    "a partir de", "economie", "promotionnel", "prix promotion", "au lieu de",
    "offre speciale", "des le", "soit", "valeur", "remise",
    "capacite", "dimensions", "garantie", "disponible en", "coloris",
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
    "balai", "serpilliere", "raclette", "pelle", "couscoussier", "menagere",
    "brosse", "ustensile", "service a epices", "porte-bouteille", "support",
    "egouttoir", "distributeur", "boite a pain", "poubelle",
    "plat de presentation", "porcelaine", "faience", "argile",
    "film alimentaire", "papier aluminium", "sac congelation", "service",
    "tirelire", "kit", "coffre-fort",
    # Matière : aucun aliment ne s'appelle « inox ». C'est ce mot, et non
    # « brochette », qui distingue les piques à brochettes des brochettes de bœuf.
    "inox",
)

DECO_TEXTILE = (
    "serviette", "serviettes", "drap", "draps", "couette", "oreiller",
    "coussin", "rideau", "rideaux", "tapis", "nappe", "pyjama", "chaussure",
    "chaussures", "vetement", "tee-shirt", "tshirt", "robe", "pantalon",
    "chemise", "chaussette", "peignoir", "bonnet", "echarpe", "cadre",
    "miroir", "vase", "bougie", "lampe", "guirlande", "decoration",
    "horloge", "tableau", "valise", "velo", "halteres", "jouet", "puzzle",
    "poupee", "trottinette", "ballon", "pistolet", "peluche", "helicoptere",
    "telecommande", "drone", "voiture rc",
    # Textile marocain et literie : hors périmètre au même titre que le reste.
    "jabador", "gandora", "djellaba", "caftan", "kaftan", "matelas", "banc",
    "sac de sport", "sac a dos", "cartable", "parasol", "transat", "piscine",
    # Cosmétique : ni nourriture, ni hygiène de base du foyer.
    "rouge a levres", "maquillage", "vernis", "mascara", "fond de teint",
    "eyeliner", "fard", "henne cheveux", "teinture",
)

# Objets, malgré un nom de consommable dans leur intitulé.
OBJETS_DE_SALLE_DE_BAIN = (
    "distributeur de savon", "porte-savon", "porte savon", "boite a savon",
    "porte-brosse", "porte-serviette", "derouleur",
)

# Zone grise : consommables non alimentaires du quotidien.
HYGIENE_ENTRETIEN = (
    "shampooing", "shampoing", "savon", "gel douche", "dentifrice",
    "deodorant", "lessive", "detergent", "javel", "nettoyant", "desinfectant",
    "liquide vaisselle", "adoucissant", "papier toilette", "essuie-tout",
    "mouchoir", "couche", "couches", "lingette", "lingettes", "coton",
    # Marques de lessive : sans elles, « Pack Tide » passait pour un aliment.
    "tide", "ariel", "omo", "persil lessive", "ajax", "mr propre", "paic",
    "brosse a dents", "rasoir jetable", "serviette hygienique", "parfum",
    "creme", "lait corporel", "cologne", "insecticide", "desodorisant",
)


def sans_accents(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def contient_mot(texte: str, termes: tuple[str, ...]) -> bool:
    """
    Recherche sur mots entiers, pluriel toléré.

    La limite de mot est indispensable — sans elle « seMOULE » matcherait
    « moule ». Mais une limite stricte fait rater les pluriels : « pyjama »
    ne reconnaîtrait pas « pyjamaS ». D'où le « s » final optionnel.
    """
    for terme in termes:
        # Pluriel possible sur CHAQUE mot : « serviettes hygiéniques » doit
        # être reconnu par « serviette hygiénique ».
        motif = r"\s+".join(re.escape(mot) + "s?" for mot in terme.split())
        if re.search(rf"(?<![a-z]){motif}(?![a-z])", texte):
            return True
    return False


def categorie(nom: str) -> str:
    s = sans_accents(nom)
    # Un nom qui se réduit à une mention de mise en page n'est pas un produit.
    depouille = re.sub(r"[^a-z ]", " ", s).strip()
    if any(depouille.startswith(f) or depouille == f for f in FRAGMENTS):
        return "fragment"
    # Nom coupé à l'extraction : « Biscuit chocolat à », « Lben à ». Une
    # préposition en fin de nom signale une phrase tronquée, pas un produit.
    if depouille.endswith((" a", " de", " en", " pour", " avec", " sur", " au")):
        return "fragment"
    if contient_mot(s, ELECTROMENAGER):
        return "electromenager"
    # L'hygiène passe avant la vaisselle pour la brosse à dents, ce qui ferait
    # du distributeur de savon un consommable. On tranche ces objets d'abord.
    if contient_mot(s, OBJETS_DE_SALLE_DE_BAIN):
        return "vaisselle"
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

    hors_perimetre = {"electromenager", "vaisselle", "deco", "fragment"}
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
