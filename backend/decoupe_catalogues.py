"""
decoupe_catalogues.py — Découpe les vignettes produit des catalogues PDF.

Les catalogues sont des pages aplaties : chaque page est une grille de produits
séparés par des gouttières blanches. La segmentation se fait en deux temps —
d'abord les rangées sur la page entière, puis les colonnes à l'intérieur de
chaque rangée (les gouttières verticales ne sont franches qu'à ce niveau).

Produit :
  vignettes/<enseigne>_p<page>_r<rangee>c<colonne>.jpg
  planches/<enseigne>_p<page>.jpg   (planche contact numérotée, pour relecture)

Usage :
    python decoupe_catalogues.py <dossier_pdf> <dossier_sortie> [--dpi 110]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

import numpy as np
import pymupdf
from PIL import Image, ImageDraw

SEUIL_BLANC = 235          # niveau de gris au-delà duquel un pixel est « blanc »
MIN_GOUTTIERE = 6          # épaisseur minimale d'une séparation, en pixels
LARGEUR_MINI = 70          # largeur minimale d'une vignette exploitable
HAUTEUR_MINI = 90


def bandes_blanches(profil: np.ndarray, seuil: float, mini: int) -> list[tuple[int, int]]:
    """Intervalles où le profil dépasse `seuil` sur au moins `mini` pixels."""
    zones, debut = [], None
    for i, v in enumerate(profil):
        if v >= seuil:
            if debut is None:
                debut = i
        elif debut is not None:
            if i - debut >= mini:
                zones.append((debut, i))
            debut = None
    if debut is not None and len(profil) - debut >= mini:
        zones.append((debut, len(profil)))
    return zones


def decoupe_page(gris: np.ndarray, marge: tuple[int, int, int, int]) -> list[tuple[int, int, int, int]]:
    """Retourne les boîtes (x0, y0, x1, y1) des vignettes détectées."""
    x0, y0, x1, y1 = marge
    zone = gris[y0:y1, x0:x1] > SEUIL_BLANC

    separations = bandes_blanches(zone.mean(axis=1), 0.94, 8)
    bornes = [0] + [(a + b) // 2 for a, b in separations] + [y1 - y0]
    rangees = [(bornes[i], bornes[i + 1]) for i in range(len(bornes) - 1)
               if bornes[i + 1] - bornes[i] >= HAUTEUR_MINI]

    boites = []
    for ya, yb in rangees:
        bande = zone[ya:yb, :]
        seps_v = bandes_blanches(bande.mean(axis=0), 0.985, MIN_GOUTTIERE)
        bv = [0] + [(a + b) // 2 for a, b in seps_v] + [x1 - x0]
        colonnes = [(bv[i], bv[i + 1]) for i in range(len(bv) - 1)
                    if bv[i + 1] - bv[i] >= LARGEUR_MINI]
        for xa, xb in colonnes:
            boites.append((x0 + xa, y0 + ya, x0 + xb, y0 + yb))
    return boites


def planche_contact(page: Image.Image, boites: list, chemin: Path) -> None:
    """Copie de la page avec les vignettes encadrées et numérotées."""
    aperçu = page.copy()
    d = ImageDraw.Draw(aperçu)
    for n, (x0, y0, x1, y1) in enumerate(boites, 1):
        d.rectangle([x0, y0, x1, y1], outline=(220, 30, 40), width=3)
        d.rectangle([x0, y0, x0 + 34, y0 + 24], fill=(220, 30, 40))
        d.text((x0 + 10, y0 + 6), str(n), fill=(255, 255, 255))
    aperçu.save(chemin, quality=85)


def main() -> None:
    dossier_pdf = Path(sys.argv[1])
    sortie = Path(sys.argv[2])
    dpi = int(sys.argv[sys.argv.index("--dpi") + 1]) if "--dpi" in sys.argv else 110

    (sortie / "vignettes").mkdir(parents=True, exist_ok=True)
    (sortie / "planches").mkdir(parents=True, exist_ok=True)

    total = 0
    for pdf in sorted(dossier_pdf.glob("*.pdf")):
        enseigne = re.sub(r"Catalogue |\.pdf", "", pdf.name)
        enseigne = enseigne.split(" du ")[0].split(" mardi")[0].strip().lower().replace(" ", "")

        doc = pymupdf.open(pdf)
        n_pages = 0
        for i, page in enumerate(doc, 1):
            pix = page.get_pixmap(dpi=dpi)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            gris = np.array(img.convert("L"))
            h, w = gris.shape

            # marge : on écarte l'en-tête et le pied de page du rendu web
            marge = (int(w * 0.06), int(h * 0.10), int(w * 0.95), int(h * 0.90))
            boites = decoupe_page(gris, marge)
            if not boites:
                continue

            for n, (x0, y0, x1, y1) in enumerate(boites, 1):
                img.crop((x0, y0, x1, y1)).save(
                    sortie / "vignettes" / f"{enseigne}_p{i:02}_{n:02}.jpg", quality=88
                )
            planche_contact(img, boites, sortie / "planches" / f"{enseigne}_p{i:02}.jpg")
            total += len(boites)
            n_pages += 1
        print(f"  {enseigne:12} {n_pages:3} pages · {total:4} vignettes cumulées")
        doc.close()

    print(f"\n[OK] {total} vignettes découpées dans {sortie}")


if __name__ == "__main__":
    main()
