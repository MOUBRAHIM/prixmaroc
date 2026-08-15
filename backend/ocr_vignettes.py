"""
ocr_vignettes.py — Appariement automatique vignette → produit, par lecture du prix.

Principe : chaque vignette de catalogue affiche son prix en gros. Plutôt que de
chercher à le lire parfaitement — le texte est blanc sur pastille rouge, et le
rouge des emballages parasite la détection — on exploite le fait que l'ensemble
des prix possibles est CONNU : ce sont ceux des produits déjà importés pour
cette enseigne.

On extrait donc tous les nombres visibles, on les confronte à cette liste, et
on ne retient la vignette que si UN SEUL prix connu correspond. L'ambiguïté est
écartée plutôt que devinée : une photo fausse est pire qu'une absence de photo.

Usage :
    DATABASE_URL="..." python ocr_vignettes.py <dossier_vignettes> [--appliquer]
"""
from __future__ import annotations

import asyncio
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import pytesseract
from PIL import Image

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

BASE_PUBLIQUE = "https://prixmaroc-api-07el.onrender.com/static/products"
DESTINATION = Path(__file__).resolve().parent / "static" / "products"

# préfixe de fichier -> enseigne en base
ENSEIGNES = {
    "bim": "BIM", "atacadao": "Atacadão",
    "carrefour": "Carrefour", "supeco": "Supeco",
}


def variantes(img: Image.Image) -> list[Image.Image]:
    """Plusieurs préparations : le prix apparaît selon les cas en blanc sur
    pastille colorée, ou en sombre sur fond clair."""
    a = np.array(img.convert("RGB")).astype(int)
    R, G, B = a[:, :, 0], a[:, :, 1], a[:, :, 2]
    sorties = []

    # 1. pastille colorée (rouge ou orange) isolée puis inversée
    masque = (R > 140) & (R - G > 55) & (R - B > 55)
    if masque.sum() > 150:
        ys, xs = np.where(masque)
        z = img.crop((xs.min(), ys.min(), xs.max() + 1, ys.max() + 1)).convert("L")
        z = z.resize((z.width * 4, z.height * 4), Image.LANCZOS)
        b = np.array(z)
        sorties.append(Image.fromarray(np.where(b > b.mean(), 0, 255).astype("uint8")))

    # 2. vignette entière, binarisée — deux passes suffisent : au-delà, le coût
    #    par vignette explose sans gain mesurable.
    g = img.convert("L")
    g = g.resize((g.width * 2, g.height * 2), Image.LANCZOS)
    b = np.array(g)
    sorties.append(Image.fromarray(np.where(b > 128, 255, 0).astype("uint8")))
    return sorties


def nombres_de(img: Image.Image) -> set[float]:
    """Tous les montants plausibles lus sur la vignette."""
    trouves: set[float] = set()
    for v in variantes(img):
        for psm in ("6",):
            try:
                txt = pytesseract.image_to_string(
                    v, config=f"--psm {psm} -c tessedit_char_whitelist=0123456789,. "
                )
            except Exception:
                continue
            txt = txt.replace(",", ".")
            # montants complets : 84.90 / 3.8
            for m in re.findall(r"\d{1,4}\.\d{1,2}", txt):
                try:
                    trouves.add(round(float(m), 2))
                except ValueError:
                    pass
            # entiers isolés : recomposés plus tard avec les décimales voisines
            for m in re.findall(r"\b\d{1,4}\b", txt):
                try:
                    trouves.add(float(m))
                except ValueError:
                    pass
    return trouves


def candidats(lus: set[float], connus: set[float]) -> set[float]:
    """
    Prix connus compatibles avec ce qui a été lu.

    Tesseract fragmente souvent « 84,90 » en « 84 » et « 90 » : un prix connu
    est donc retenu si sa valeur exacte, sa partie entière ou ses centimes
    figurent parmi les nombres lus.
    """
    retenus = set()
    for p in connus:
        entier = float(int(p))
        centimes = float(round((p - int(p)) * 100))
        if p in lus:
            retenus.add(p)
        elif entier in lus and (centimes in lus or centimes == 0):
            retenus.add(p)
    return retenus


async def main() -> None:
    source = Path(sys.argv[1])
    appliquer = "--appliquer" in sys.argv
    DESTINATION.mkdir(parents=True, exist_ok=True)

    async with Session() as db:
        # prix connus par enseigne -> produits concernés
        lignes = (await db.execute(text("""
            SELECT s.name AS enseigne, pr.price::float AS prix, p.id, p.name, p.image_url
              FROM prices pr
              JOIN stores s   ON s.id = pr.store_id
              JOIN products p ON p.id = pr.product_id
             WHERE p.is_active
        """))).all()

        par_enseigne: dict[str, dict[float, set[tuple]]] = defaultdict(lambda: defaultdict(set))
        for e, prix, pid, nom, img in lignes:
            par_enseigne[e][round(prix, 2)].add((pid, nom, img))

        fichiers = sorted(source.glob("*.jpg"))
        poses = ambigus = illisibles = deja = 0

        for f in fichiers:
            enseigne = ENSEIGNES.get(f.name.split("_")[0])
            if not enseigne or enseigne not in par_enseigne:
                continue
            connus = par_enseigne[enseigne]

            lus = nombres_de(Image.open(f))
            if not lus:
                illisibles += 1
                continue

            possibles = candidats(lus, set(connus))
            # on ne garde que les prix menant à UN seul produit
            produits = {p for prix in possibles for p in connus[prix]}
            if len(produits) != 1:
                ambigus += 1
                continue

            pid, nom, img_actuelle = produits.pop()
            if img_actuelle:
                deja += 1
                continue

            if appliquer:
                shutil.copyfile(f, DESTINATION / f"{pid}.jpg")
                await db.execute(
                    text("UPDATE products SET image_url = :u WHERE id = :i"),
                    {"u": f"{BASE_PUBLIQUE}/{pid}.jpg", "i": pid},
                )
            poses += 1
            print(f"  #{pid:5} {nom[:42]:44} <- {f.name}")

        if appliquer:
            await db.commit()

        print(f"\n[{'APPLIQUE' if appliquer else 'SIMULATION'}] {poses} appariements sûrs · "
              f"{ambigus} ambigus · {illisibles} illisibles · {deja} déjà illustrés "
              f"(sur {len(fichiers)} vignettes)")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
