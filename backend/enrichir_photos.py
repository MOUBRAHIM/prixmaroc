"""
enrichir_photos.py — Photos officielles depuis Open Food Facts.

Le moteur de recherche d'Open Food Facts renvoie toujours un résultat, même
sans rapport : « Huile de table Nounine » remonte « Fleur de sel », et
« Sardines Aïcha » remonte « Mayonnaise ». Prendre le premier résultat colle
donc de fausses photos — erreur déjà commise sur ce catalogue, vingt-huit
fois, et qu'il a fallu défaire à la main.

Claude relit donc chaque candidat et répond lequel est le même produit, ou
aucun. Une fiche sans photo vaut mieux qu'une fiche avec la photo d'autre
chose : l'application affiche alors une vignette illustrée par catégorie.

Usage :
    python enrichir_photos.py [--appliquer] [--produits=N]
"""
from __future__ import annotations

import asyncio
import json
import re
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

import anthropic
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Product
from app.services.reponse_claude import texte_de

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

MODELE = "claude-haiku-4-5-20251001"
RECHERCHE = "https://search.openfoodfacts.org/search"
AGENT = {"User-Agent": "PrixMaroc/1.0 (https://github.com/MOUBRAHIM/prixmaroc)"}

CANDIDATS_MAX = 4
TAILLE_LOT = 12          # produits par appel de vérification
PAUSE = 1.2              # respect du rythme demandé par Open Food Facts

CONSIGNE = """Tu vérifies si une photo de produit correspond au bon article.

On te donne des produits d'un supermarché marocain. Pour chacun, des candidats
trouvés dans une base de photos. Dis lequel est LE MÊME produit.

Réponds UNIQUEMENT par un tableau JSON :
[{"i": 0, "candidat": 2}, {"i": 1, "candidat": null}]

Règles :
- "i" est le numéro du produit, "candidat" le numéro du candidat retenu.
- Réponds null dès qu'il y a un doute. Une photo fausse est bien pire qu'une
  absence de photo : l'utilisateur croirait acheter autre chose.
- Le même aliment sous une autre marque n'est PAS le même produit.
- Une variante proche de la même marque est acceptable : « Couscous Dari fin »
  convient pour « Couscous Dari », « Yaourt Activia nature » pour
  « Yaourt Activia ».
- Un format différent de la même référence est acceptable (1 L pour 2 L)."""


async def candidats(client: httpx.AsyncClient, nom: str) -> list[dict]:
    """Références portant une photo, pour ce nom de produit."""
    try:
        r = await client.get(RECHERCHE, params={
            "q": nom, "page_size": 8,
            "fields": "product_name,product_name_fr,brands,image_front_url",
        }, headers=AGENT, timeout=25)
        r.raise_for_status()
        hits = r.json().get("hits") or []
    except Exception:
        return []

    sortie = []
    for h in hits:
        photo = h.get("image_front_url")
        titre = (h.get("product_name_fr") or h.get("product_name") or "").strip()
        if photo and titre:
            # « brands » arrive tantôt en chaîne « A, B », tantôt en liste.
            brut = h.get("brands") or ""
            marque = (brut[0] if isinstance(brut, list) and brut
                      else str(brut).split(",")[0]).strip()
            sortie.append({"titre": titre[:90], "marque": marque[:40], "photo": photo})
        if len(sortie) >= CANDIDATS_MAX:
            break
    return sortie


async def verifier(claude, lot: list[tuple[Product, list[dict]]]) -> dict[int, str]:
    """Numéro du produit → adresse de la photo retenue."""
    lignes = []
    for i, (p, cands) in enumerate(lot):
        lignes.append(f"Produit {i} : {p.name}")
        for j, c in enumerate(cands):
            marque = f" — marque {c['marque']}" if c["marque"] else ""
            lignes.append(f"   candidat {j} : {c['titre']}{marque}")
    try:
        reponse = await claude.messages.create(
            model=MODELE, max_tokens=1024, system=CONSIGNE,
            messages=[{"role": "user", "content": "\n".join(lignes)}],
        )
    except Exception as e:
        print(f"    [erreur] {type(e).__name__}")
        return {}

    brut = re.sub(r"^```(?:json)?|```$", "", texte_de(reponse), flags=re.MULTILINE).strip()
    try:
        donnees = json.loads(brut)
    except json.JSONDecodeError:
        return {}
    if not isinstance(donnees, list):
        return {}

    retenus: dict[int, str] = {}
    for d in donnees:
        if not isinstance(d, dict):
            continue
        try:
            i, j = int(d.get("i")), d.get("candidat")
        except (TypeError, ValueError):
            continue
        if j is None or not 0 <= i < len(lot):
            continue
        try:
            j = int(j)
        except (TypeError, ValueError):
            continue
        cands = lot[i][1]
        if 0 <= j < len(cands):
            retenus[i] = cands[j]["photo"]
    return retenus


async def main() -> None:
    appliquer = "--appliquer" in sys.argv
    limite = next((int(a.split("=")[1]) for a in sys.argv if a.startswith("--produits=")), 10_000)

    if not settings.ANTHROPIC_API_KEY:
        print("[STOP] ANTHROPIC_API_KEY absente.")
        return
    claude = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY,
                                      max_retries=1, timeout=60.0)

    async with Session() as db:
        produits = list((await db.execute(
            select(Product)
            .where(Product.is_active.is_(True), Product.image_url.is_(None))
            .order_by(Product.id)
        )).scalars())[:limite]
        print(f"{len(produits)} produits sans photo\n")

        poses = sans_candidat = refuses = 0
        async with httpx.AsyncClient(follow_redirects=True) as web:
            for n in range(0, len(produits), TAILLE_LOT):
                tranche = produits[n:n + TAILLE_LOT]
                lot: list[tuple[Product, list[dict]]] = []
                for p in tranche:
                    c = await candidats(web, p.name)
                    if c:
                        lot.append((p, c))
                    else:
                        sans_candidat += 1
                    await asyncio.sleep(PAUSE)

                if not lot:
                    continue
                retenus = await verifier(claude, lot)
                refuses += len(lot) - len(retenus)

                for i, url in retenus.items():
                    produit = lot[i][0]
                    print(f"    {produit.name[:42]:44} <- {url.split('/')[-1][:26]}")
                    if appliquer:
                        produit.image_url = url
                    poses += 1
                if appliquer:
                    await db.commit()
                print(f"  {min(n + TAILLE_LOT, len(produits)):4}/{len(produits)} — "
                      f"{poses} posées · {refuses} refusées · {sans_candidat} sans candidat")

        print(f"\n[{'APPLIQUÉ' if appliquer else 'SIMULATION'}] {poses} photos")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
