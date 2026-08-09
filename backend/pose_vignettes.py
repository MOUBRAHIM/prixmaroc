"""
pose_vignettes.py — Rattache les vignettes découpées aux produits en base.

Chaque entrée du fichier de correspondance décrit une vignette relevée sur une
planche de catalogue : enseigne, fichier découpé, mot-clé du nom et prix affiché.
Le prix est le discriminant fort — il provient du même catalogue que le produit
importé, donc l'appariement (enseigne + mot-clé + prix) est fiable.

La vignette retenue est copiée dans backend/static/products/<id>.jpg et servie
par l'API : pas de stockage externe à provisionner.

Format du fichier (JSON) :
  [ {"enseigne": "BIM", "fichier": "bim_p08_04.jpg", "mot": "Spaghetti", "prix": 11.9}, ... ]

Usage :
    DATABASE_URL="..." python pose_vignettes.py <dossier_vignettes> <correspondances.json>
"""
from __future__ import annotations

import asyncio
import json
import shutil
import sys
from pathlib import Path

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

BASE_PUBLIQUE = "https://prixmaroc-api-07el.onrender.com/static/products"
DESTINATION = Path(__file__).resolve().parent / "static" / "products"

REQUETE = text("""
    SELECT p.id, p.name
      FROM products p
      JOIN prices pr ON pr.product_id = p.id
      JOIN stores s  ON s.id = pr.store_id
     WHERE p.is_active
       AND s.name = :enseigne
       AND p.name ILIKE :motif
       AND ABS(pr.price - :prix) < 0.01
     LIMIT 1
""")


async def main() -> None:
    source = Path(sys.argv[1])
    correspondances = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    DESTINATION.mkdir(parents=True, exist_ok=True)

    poses, introuvables, absents = 0, [], []

    async with Session() as db:
        for c in correspondances:
            fichier = source / c["fichier"]
            if not fichier.exists():
                absents.append(c["fichier"])
                continue

            ligne = (await db.execute(REQUETE, {
                "enseigne": c["enseigne"],
                "motif": f"%{c['mot']}%",
                "prix": c["prix"],
            })).first()

            if not ligne:
                introuvables.append(f"{c['mot']} @ {c['prix']} ({c['enseigne']})")
                continue

            pid, nom = ligne
            shutil.copyfile(fichier, DESTINATION / f"{pid}.jpg")
            await db.execute(
                text("UPDATE products SET image_url = :url WHERE id = :id"),
                {"url": f"{BASE_PUBLIQUE}/{pid}.jpg", "id": pid},
            )
            poses += 1
            print(f"  #{pid:5} {nom[:44]:46} <- {c['fichier']}")

        await db.commit()

    print(f"\n[OK] {poses} vignettes posées")
    if introuvables:
        print(f"  {len(introuvables)} sans produit correspondant : {introuvables[:6]}")
    if absents:
        print(f"  {len(absents)} fichiers manquants : {absents[:6]}")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
