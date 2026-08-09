"""
import_magasins_osm.py — Importe les vrais magasins depuis OpenStreetMap.

Les magasins présents en base avaient des coordonnées saisies à la main et ne
couvraient que 11 villes. Ce script interroge Overpass ville par ville — une
requête sur tout le Maroc dépasse systématiquement le délai du service — et
n'insère que les enseignes pour lesquelles nous avons des prix.

Les magasins déjà présents ne sont pas dupliqués : on rapproche par proximité
géographique (moins de 200 m) et par enseigne.

Usage :
    DATABASE_URL="postgresql://..." python import_magasins_osm.py [--test]
"""
from __future__ import annotations

import asyncio
import math
import re
import sys
import time

import httpx

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import Store

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

OVERPASS = "https://overpass-api.de/api/interpreter"
ENTETES = {"User-Agent": "PrixMaroc/1.0 (contact@prixmaroc.ma)"}
PAUSE = 6.0        # Overpass renvoie 429 si on enchaîne trop vite
RAYON_M = 15000

# Villes couvertes (nom, latitude, longitude)
VILLES = [
    ("Casablanca", 33.5731, -7.5898), ("Rabat", 34.0209, -6.8416),
    ("Salé", 34.0531, -6.7985), ("Témara", 33.9287, -6.9067),
    ("Bouznika", 33.7891, -7.1594), ("Mohammedia", 33.6861, -7.3829),
    ("Kénitra", 34.2610, -6.5802), ("Marrakech", 31.6295, -7.9811),
    ("Fès", 34.0331, -5.0003), ("Meknès", 33.8935, -5.5473),
    ("Tanger", 35.7595, -5.8340), ("Tétouan", 35.5785, -5.3684),
    ("Agadir", 30.4278, -9.5981), ("Oujda", 34.6814, -1.9086),
    ("El Jadida", 33.2316, -8.5007), ("Safi", 32.2994, -9.2372),
    ("Béni Mellal", 32.3373, -6.3498), ("Nador", 35.1681, -2.9335),
    ("Khouribga", 32.8811, -6.9063), ("Settat", 33.0010, -7.6166),
    ("Berrechid", 33.2655, -7.5877), ("Larache", 35.1932, -6.1557),
    ("Essaouira", 31.5085, -9.7595), ("Ouarzazate", 30.9335, -6.9370),
    ("Errachidia", 31.9314, -4.4245), ("Taza", 34.2100, -4.0100),
    ("Khémisset", 33.8242, -6.0658), ("Berkane", 34.9218, -2.3200),
    ("Guelmim", 28.9870, -10.0574), ("Laâyoune", 27.1536, -13.2033),
]

# Enseignes retenues : celles pour lesquelles nous avons des prix,
# plus les grandes enseignes marocaines déjà connues de la base.
ENSEIGNES = {
    "marjane": "Marjane", "acima": "Acima", "carrefour": "Carrefour",
    "label": "Label'Vie", "bim": "BIM", "atacad": "Atacadão",
    "aswak": "Aswak Assalam", "kazyon": "Kazyon", "supeco": "Supeco",
}


def enseigne_de(tags: dict) -> str | None:
    texte = " ".join(str(tags.get(k, "")) for k in ("brand", "name", "operator")).lower()
    for cle, nom in ENSEIGNES.items():
        if cle in texte:
            return nom
    return None


def distance_km(a_lat: float, a_lon: float, b_lat: float, b_lon: float) -> float:
    R = 6371.0
    dlat, dlon = math.radians(b_lat - a_lat), math.radians(b_lon - a_lon)
    x = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(a_lat)) * math.cos(math.radians(b_lat)) * math.sin(dlon / 2) ** 2)
    return 2 * R * math.asin(math.sqrt(x))


def slugifier(texte: str) -> str:
    s = texte.lower()
    for a, b in [("à","a"),("â","a"),("é","e"),("è","e"),("ê","e"),("î","i"),("ô","o"),
                 ("û","u"),("ù","u"),("ç","c"),("'","-"),("’","-")]:
        s = s.replace(a, b)
    return re.sub(r"-+", "-", re.sub(r"[^a-z0-9]+", "-", s)).strip("-")[:240]


def interroger(ville: str, lat: float, lon: float) -> list[dict]:
    requete = (
        f'[out:json][timeout:60];'
        f'nwr["shop"~"supermarket|hypermarket"](around:{RAYON_M},{lat},{lon});'
        f'out center tags;'
    )
    for essai in range(3):
        try:
            r = httpx.post(OVERPASS, data={"data": requete}, headers=ENTETES, timeout=90)
            if r.status_code == 200 and "json" in (r.headers.get("content-type") or ""):
                return r.json().get("elements", [])
            if r.status_code == 429:
                time.sleep(15)
                continue
        except Exception:
            time.sleep(8)
    return []


async def main() -> None:
    test = "--test" in sys.argv

    async with Session() as db:
        existants = (await db.execute(select(Store))).scalars().all()
        connus = [(s, s.name) for s in existants]
        slugs = {s.slug for s in existants}

        ajoutes = completes = 0
        for ville, lat, lon in VILLES:
            elements = interroger(ville, lat, lon)
            retenus = 0
            for el in elements:
                tags = el.get("tags") or {}
                enseigne = enseigne_de(tags)
                if not enseigne:
                    continue
                y = el.get("lat") or (el.get("center") or {}).get("lat")
                x = el.get("lon") or (el.get("center") or {}).get("lon")
                if y is None or x is None:
                    continue

                # Déjà connu ? (même enseigne à moins de 200 m)
                doublon = next(
                    (s for s, nom in connus
                     if nom == enseigne and s.latitude is not None
                     and distance_km(float(s.latitude), float(s.longitude), y, x) < 0.2),
                    None,
                )
                if doublon:
                    continue

                # Enseigne connue mais sans coordonnées (Kazyon, Supeco) : on la complète
                orpheline = next(
                    (s for s, nom in connus if nom == enseigne and s.latitude is None), None
                )
                if orpheline:
                    orpheline.latitude, orpheline.longitude = y, x
                    orpheline.city = ville
                    orpheline.address = tags.get("addr:street") or tags.get("addr:full")
                    completes += 1
                    connus = [(s, n) for s, n in connus if s is not orpheline] + [(orpheline, enseigne)]
                    retenus += 1
                    continue

                base = slugifier(f"{enseigne}-{ville}-{y:.4f}-{x:.4f}")
                if base in slugs:
                    continue
                slugs.add(base)
                nouveau = Store(
                    name=enseigne, slug=base,
                    address=tags.get("addr:street") or tags.get("addr:full"),
                    city=ville, latitude=y, longitude=x, is_active=True,
                )
                db.add(nouveau)
                connus.append((nouveau, enseigne))
                ajoutes += 1
                retenus += 1

            print(f"  {ville:14} {len(elements):4} commerces · {retenus:3} retenus")
            if not test:
                await db.commit()
            time.sleep(PAUSE)

        if not test:
            await db.commit()
        total = (await db.execute(select(Store))).scalars().all()
        villes = {s.city for s in total if s.city}
        print(f"\n[{'TEST' if test else 'OK'}] {ajoutes} magasins ajoutés · "
              f"{completes} enseignes complétées · {len(total)} magasins, {len(villes)} villes")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
