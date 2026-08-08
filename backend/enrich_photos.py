"""
enrich_photos.py — Associe de vraies photos aux produits alimentaires.

Source : Open Food Facts (photos contribuées, licence ouverte CC-BY-SA).
On interroge le moteur `search.openfoodfacts.org` — l'API v2 `/api/v2/search`
n'accepte PAS la recherche plein texte et renvoie des résultats arbitraires.

Règles de prudence (une mauvaise photo est pire que pas de photo) :
  • on écarte les produits non alimentaires (électroménager, textile, maison) ;
  • on exige un recouvrement de mots >= SEUIL entre notre nom et le résultat ;
  • on exige que le résultat ait effectivement une image ;
  • sans correspondance sûre, le produit garde sa vignette illustrée.

Usage :
    DATABASE_URL="postgresql://..." python enrich_photos.py [--limite N] [--test]
"""
from __future__ import annotations

import asyncio
import re
import sys
import time
import unicodedata

import httpx

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Product

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

RECHERCHE = "https://search.openfoodfacts.org/search"
ENTETES = {"User-Agent": "PrixMaroc/1.0 (contact@prixmaroc.ma)"}
SEUIL = 0.85
PAUSE = 1.1  # respect du service public

# Produits qui ne sont pas des denrées : jamais de photo alimentaire dessus.
NON_ALIMENTAIRE = (
    "cafetière", "cafetiere", "friteuse", "air fryer", "airfryer", "machine",
    "micro-onde", "micro onde", "grille-pain", "presse-agrumes", "extracteur",
    "plancha", "barbecue", "rechaud", "réchaud", "gaufrier", "crepiere", "crêpière",
    "réfrigérateur", "refrigerateur", "congélateur", "congelateur", "aspirateur",
    "téléviseur", "televiseur", " tv ", "smartphone", "samsung", "xiaomi", "iphone",
    "ordinateur", "casque", "écouteur", "ecouteur", "montre", "ventilateur",
    "chauffage", "radiateur", "mixeur", "blender", "robot", "bouilloire",
    "théière", "theiere", "casserole", "poêle", "poele", "marmite", "cocotte",
    "assiette", "verre", "bocal", "bocaux", "couvert", "couteau", "plateau",
    "pyjama", "chaussure", "tapis", "drap", "couette", "serviette", "peignoir",
    "sac ", "valise", "vélo", "velo", "chaise", "table", "meuble", "étagère",
    "lampe", "rideau", "coussin", "jouet", "puzzle", "parfum", "shampooing",
    "savon", "dentifrice", "lessive", "détergent", "detergent", "javel",
    "couche", "lingette", "papier toilette", "essuie",
)

MOTS_VIDES = {
    "les", "des", "avec", "sans", "pour", "pack", "lot", "the", "une", "aux",
    "par", "sur", "kit", "set", "pcs", "piece", "pieces",
}


def sans_accents(texte: str) -> str:
    t = unicodedata.normalize("NFKD", texte.lower())
    return "".join(c for c in t if not unicodedata.combining(c))


def racine(mot: str) -> str:
    """Rapproche singulier et pluriel : « biscuit » et « biscuits » s'équivalent."""
    return mot[:-1] if len(mot) > 4 and mot.endswith("s") else mot


def mots(texte: str) -> set[str]:
    bruts = set(re.findall(r"[a-z]{3,}", sans_accents(texte))) - MOTS_VIDES
    return {racine(m) for m in bruts}


def est_alimentaire(nom: str) -> bool:
    n = f" {sans_accents(nom)} "
    return not any(sans_accents(k) in n for k in NON_ALIMENTAIRE)


def requete_depuis(nom: str) -> str:
    """Retire les contenances (1 kg, 500 ml, x6…) qui polluent la recherche."""
    r = re.sub(r"\b\d+[.,]?\d*\s*(kg|g|l|ml|cl|cm|mm)\b", " ", nom, flags=re.I)
    r = re.sub(r"[x×]\s*\d+", " ", r)
    r = re.sub(r"\d+", " ", r)
    return re.sub(r"\s+", " ", r).strip()


def photo_de(hit: dict) -> str | None:
    """URL de la photo de face, si la fiche en possède une."""
    for champ in ("image_front_url", "image_url", "image_front_small_url"):
        url = hit.get(champ)
        if url:
            return str(url)
    return None


def meilleur_resultat(nom: str, hits: list[dict]) -> tuple[dict | None, float]:
    """
    Meilleur candidat PARMI CEUX QUI ONT UNE PHOTO. Beaucoup de fiches Open Food
    Facts sont sans image : retenir le mieux noté puis constater l'absence de
    photo ferait perdre des correspondances valables un rang plus bas.
    """
    requete = requete_depuis(nom)
    reference = mots(requete)
    if not reference:
        return None, 0.0

    # Le premier mot significatif porte le TYPE du produit (biscuit, huile,
    # yaourt…). S'il est absent du candidat, on refuse : c'est ce qui évite
    # d'illustrer un « Biscuit céréales » avec une « Barre de céréales ».
    premiers = [racine(m) for m in re.findall(r"[a-z]{3,}", sans_accents(requete)) if m not in MOTS_VIDES]
    type_produit = premiers[0] if premiers else None

    meilleur, score_max = None, 0.0
    for h in hits:
        if not photo_de(h):
            continue
        candidat = mots(str(h.get("product_name") or "")) | mots(str(h.get("brands") or ""))
        if type_produit and type_produit not in candidat:
            continue
        score = len(reference & candidat) / len(reference)
        if score > score_max:
            meilleur, score_max = h, score
    return meilleur, score_max


async def main() -> None:
    limite = None
    if "--limite" in sys.argv:
        limite = int(sys.argv[sys.argv.index("--limite") + 1])
    test = "--test" in sys.argv

    async with Session() as db:
        produits = (await db.execute(
            select(Product).where(Product.is_active.is_(True), Product.image_url.is_(None))
        )).scalars().all()

        candidats = [p for p in produits if est_alimentaire(p.name)]
        if limite:
            candidats = candidats[:limite]

        print(f"{len(produits)} produits sans photo · {len(candidats)} alimentaires à traiter")

        trouvees = rejets = erreurs = 0
        with httpx.Client(timeout=40, headers=ENTETES, follow_redirects=True) as client:
            for i, p in enumerate(candidats, 1):
                try:
                    r = client.get(RECHERCHE, params={"q": requete_depuis(p.name), "page_size": 5})
                    if "json" not in (r.headers.get("content-type") or ""):
                        erreurs += 1
                        continue
                    hits = r.json().get("hits", [])
                except Exception:
                    erreurs += 1
                    time.sleep(PAUSE)
                    continue

                best, score = meilleur_resultat(p.name, hits)
                image = photo_de(best) if best else None

                if best and score >= SEUIL and image:
                    if not test:
                        p.image_url = image
                    trouvees += 1
                    print(f"  [{i}/{len(candidats)}] {score:.2f} {p.name[:40]:42} -> {str(best.get('product_name'))[:32]}")
                else:
                    rejets += 1

                if i % 40 == 0 and not test:
                    await db.commit()
                time.sleep(PAUSE)

        if not test:
            await db.commit()

        print(f"\n[{'TEST' if test else 'OK'}] {trouvees} photos associées · "
              f"{rejets} sans correspondance sûre · {erreurs} erreurs API")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
