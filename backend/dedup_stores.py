#!/usr/bin/env python3
"""
Dédoublonnage des magasins en base.

Critères de doublon :
  - Même chaîne (même préfixe de nom) ET même ville
  - Distance GPS < 500m

Action : garde le magasin avec le plus de prix associés, supprime les autres.
Puis liste les magasins de Bouznika présents en base.

Usage :
  python dedup_stores.py           # mode réel
  python dedup_stores.py --dry-run # affiche sans supprimer
"""
from __future__ import annotations

import asyncio
import math
import sys
import unicodedata
import re
import argparse
import io

# Fix encodage console Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, __file__.rsplit("\\", 1)[0] if "\\" in __file__ else __file__.rsplit("/", 1)[0])

from sqlalchemy import select, func, delete
from app.db import AsyncSessionLocal
from app.models.store import Store
from app.models.price import Price


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def _normalize(name: str) -> str:
    """Normalise un nom de magasin : minuscules, sans accents, sans ponctuation."""
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^\w\s]", "", name.lower()).strip()


def _chain_prefix(name: str) -> str:
    """Extrait le nom de chaîne (premier mot)."""
    n = _normalize(name)
    for prefix in ["marjane", "carrefour", "labelvie", "label vie", "bim", "acima", "atacadao", "kazyon", "sopreco"]:
        if prefix in n:
            return prefix
    return n.split()[0] if n.split() else n


async def dedup(dry_run: bool = False):
    async with AsyncSessionLocal() as db:
        # Charger tous les magasins actifs avec coords
        result = await db.execute(
            select(Store).where(Store.latitude != None, Store.longitude != None).order_by(Store.id)
        )
        stores = result.scalars().all()
        print(f"[Dedup] {len(stores)} magasins actifs avec coordonnees GPS")

        # Compter les prix par magasin
        cnt_result = await db.execute(
            select(Price.store_id, func.count(Price.id).label("cnt"))
            .group_by(Price.store_id)
        )
        price_counts = {row.store_id: row.cnt for row in cnt_result.all()}

        to_delete: set[int] = set()
        groups_found = 0

        for i, s1 in enumerate(stores):
            if s1.id in to_delete:
                continue
            chain1 = _chain_prefix(s1.name)
            city1 = (s1.city or "").lower().strip()

            for s2 in stores[i+1:]:
                if s2.id in to_delete:
                    continue
                chain2 = _chain_prefix(s2.name)
                city2 = (s2.city or "").lower().strip()

                # Meme chaine, meme ville
                if chain1 != chain2 or city1 != city2:
                    continue

                # Distance < 500m
                dist = _haversine_km(
                    float(s1.latitude), float(s1.longitude),
                    float(s2.latitude), float(s2.longitude)
                )
                if dist > 0.5:
                    continue

                # Doublon detecte
                groups_found += 1
                cnt1 = price_counts.get(s1.id, 0)
                cnt2 = price_counts.get(s2.id, 0)

                # Garder celui avec le plus de prix, sinon le plus ancien (id le plus petit)
                if cnt2 > cnt1:
                    victim = s1
                    winner = s2
                else:
                    victim = s2
                    winner = s1

                to_delete.add(victim.id)
                print(
                    f"  [DOUBLON] '{victim.name}' (id={victim.id}, {price_counts.get(victim.id,0)} prix, "
                    f"dist={dist*1000:.0f}m) "
                    f"-> supprime au profit de '{winner.name}' (id={winner.id}, "
                    f"{price_counts.get(winner.id,0)} prix)"
                )

        print(f"\n[Dedup] {groups_found} doublon(s) detecte(s), {len(to_delete)} a supprimer")

        if to_delete:
            if dry_run:
                print("[Dedup] DRY-RUN : aucune suppression effectuee")
            else:
                # Supprimer les prix des doublons d'abord
                await db.execute(delete(Price).where(Price.store_id.in_(to_delete)))
                # Supprimer les magasins
                await db.execute(delete(Store).where(Store.id.in_(to_delete)))
                await db.commit()
                print(f"[Dedup] {len(to_delete)} magasin(s) supprime(s) avec leurs prix")
        else:
            print("[Dedup] Aucun doublon - base propre")

        # Verifier les magasins de Bouznika
        print("\n" + "="*60)
        print("MAGASINS DE BOUZNIKA en base :")
        bouznika_result = await db.execute(
            select(Store).where(Store.city.ilike("%bouznika%"))
        )
        bouznika_stores = bouznika_result.scalars().all()
        if bouznika_stores:
            for s in bouznika_stores:
                n_prix = price_counts.get(s.id, 0)
                print(f"  OK  {s.name} (lat={s.latitude}, lng={s.longitude}) — {n_prix} prix")
        else:
            print("  AUCUN magasin de Bouznika en base !")
            print("  --> Executez : python seed_stores_real.py")

        print("="*60)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Affiche sans supprimer")
    args = parser.parse_args()
    asyncio.run(dedup(dry_run=args.dry_run))
