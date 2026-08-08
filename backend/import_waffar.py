"""
import_waffar.py — Remplace les prix générés par de VRAIS prix de catalogue.

Source : export Waffar (959 lignes) — relevés de catalogues promotionnels de
7 enseignes marocaines, avec période de validité.

Ce que fait le script :
  1. Nettoie et filtre le CSV (l'extraction contient des fragments : « Prix »,
     « au lieu de », morceaux de montants « : 29 »…).
  2. Crée les enseignes manquantes (Kazyon, Supeco) — sans coordonnées GPS,
     car on ne connaît pas leurs adresses réelles.
  3. Supprime TOUS les prix existants (ils étaient générés aléatoirement).
  4. Insère les prix réels, source=MANUAL (import de catalogue, pas scraping),
     recorded_at = date de début de validité.
  5. Désactive les produits qui n'ont aucun prix réel, pour ne rien afficher
     de fictif.

Un prix de catalogue est national : il est rattaché à chaque magasin de
l'enseigne concernée.

Usage :
    DATABASE_URL="postgresql://..." python import_waffar.py <chemin_csv>
"""
from __future__ import annotations

import asyncio
import csv
import re
import sys
from datetime import datetime, timezone
from decimal import Decimal

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import delete, select, func
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Price, Product, Store
from app.models.price import PriceSource

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

# Fragments d'extraction à écarter
FRAGMENTS = {
    "prix", "au lieu de", "est proposé à", "est proposée à", "prix promotion",
    "est disponible à", "prix promotionnel", "est également proposé à",
    "soit", "dont",
}

# Enseigne du CSV -> nom en base
ENSEIGNES = {
    "BIM": "BIM",
    "Kazyon": "Kazyon",
    "Carrefour": "Carrefour",
    "Marjane": "Marjane",
    "Aswak Assalam": "Aswak Assalam",
    "Atacadao": "Atacadão",
    "Supeco": "Supeco",
}


def nettoyer(nom: str) -> str:
    nom = nom.replace("’", "'").strip()
    nom = re.sub(r"^[\s:;,–—-]+", "", nom)
    nom = re.sub(r"[\s:;,–—-]+$", "", nom)
    return re.sub(r"\s+", " ", nom).strip()


def rejeter(nom: str, prix_brut: str) -> str | None:
    if len(nom) < 6:
        return "trop court"
    if nom.lower() in FRAGMENTS:
        return "fragment"
    if not re.search(r"[A-Za-zÀ-ÿ]{3}", nom):
        return "sans mot"
    try:
        p = float(prix_brut.replace(",", "."))
    except ValueError:
        return "prix illisible"
    if not (0.5 <= p <= 20_000):
        return "prix hors bornes"
    return None


def slugifier(nom: str) -> str:
    s = nom.lower()
    for a, b in [("à","a"),("â","a"),("ä","a"),("é","e"),("è","e"),("ê","e"),("ë","e"),
                 ("î","i"),("ï","i"),("ô","o"),("ö","o"),("ù","u"),("û","u"),("ü","u"),
                 ("ç","c"),("'","-")]:
        s = s.replace(a, b)
    s = re.sub(r"[^a-z0-9]+", "-", s)
    return re.sub(r"-+", "-", s).strip("-")[:480]


def taille(nom: str) -> str | None:
    m = re.search(r"(\d+(?:[.,]\d+)?)\s*(kg|g|l|ml|cl|pcs|pièces?)\b", nom, re.I)
    return f"{m.group(1)}{m.group(2).lower()}" if m else None


def date_de(txt: str) -> datetime:
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(txt.strip(), fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


async def main(chemin: str) -> None:
    with open(chemin, encoding="utf-8-sig") as f:
        lignes = list(csv.DictReader(f, delimiter=";"))

    retenues, rejets = [], {}
    for r in lignes:
        nom = nettoyer(r["Produit"])
        motif = rejeter(nom, r["Prix_DH"])
        if motif:
            rejets[motif] = rejets.get(motif, 0) + 1
            continue
        retenues.append({
            "nom": nom,
            "prix": float(r["Prix_DH"].replace(",", ".")),
            "enseigne": ENSEIGNES.get(r["Enseigne"].strip(), r["Enseigne"].strip()),
            "debut": date_de(r["Date_Debut"]),
            "fin": date_de(r["Date_Fin"]).date(),
        })

    print(f"CSV : {len(retenues)} lignes retenues sur {len(lignes)} (rejets : {rejets})")

    async with Session() as db:
        # ── Enseignes ──────────────────────────────────────────────────────
        magasins = (await db.execute(select(Store))).scalars().all()
        par_enseigne: dict[str, list[Store]] = {}
        for m in magasins:
            par_enseigne.setdefault(m.name, []).append(m)

        for enseigne in {l["enseigne"] for l in retenues}:
            if enseigne not in par_enseigne:
                s = Store(
                    name=enseigne,
                    slug=slugifier(enseigne),
                    city=None, latitude=None, longitude=None,  # adresse réelle inconnue
                    is_active=True,
                )
                db.add(s)
                await db.flush()
                par_enseigne[enseigne] = [s]
                print(f"  + enseigne créée : {enseigne} (sans coordonnées)")

        # ── Purge des prix générés ─────────────────────────────────────────
        avant = (await db.execute(select(func.count()).select_from(Price))).scalar()
        await db.execute(delete(Price))
        print(f"  - {avant} prix générés supprimés")

        # ── Produits ───────────────────────────────────────────────────────
        existants = {p.slug: p for p in (await db.execute(select(Product))).scalars().all()}
        crees = 0
        for l in retenues:
            slug = slugifier(l["nom"])
            if slug not in existants:
                p = Product(name=l["nom"], slug=slug, unit_size=taille(l["nom"]), is_active=True)
                db.add(p)
                await db.flush()
                existants[slug] = p
                crees += 1
            l["produit"] = existants[slug]
        print(f"  + {crees} produits créés")

        # ── Prix réels ─────────────────────────────────────────────────────
        inseres = 0
        for l in retenues:
            for magasin in par_enseigne[l["enseigne"]]:
                db.add(Price(
                    product_id=l["produit"].id,
                    store_id=magasin.id,
                    price=Decimal(str(round(l["prix"], 2))),
                    currency="MAD",
                    is_promo=False,          # statut promo non vérifiable
                    promo_end=l["fin"],      # fin de validité du catalogue
                    source=PriceSource.MANUAL,
                    recorded_at=l["debut"],
                ))
                inseres += 1
        await db.commit()
        print(f"  + {inseres} prix réels insérés")

        # ── Produits sans prix réel : désactivés ───────────────────────────
        sans_prix = (await db.execute(
            select(Product).where(~Product.id.in_(select(Price.product_id).distinct()))
        )).scalars().all()
        for p in sans_prix:
            p.is_active = False
        await db.commit()
        print(f"  ~ {len(sans_prix)} produits sans prix réel désactivés")

        actifs = (await db.execute(
            select(func.count()).select_from(Product).where(Product.is_active.is_(True))
        )).scalar()
        print(f"\n[OK] catalogue actif : {actifs} produits, {inseres} prix reels")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1]))
