"""
open_food_facts.py — Fiche produit à partir d'un code-barres.

Open Food Facts est une base ouverte et collaborative qui couvre correctement
le marché marocain : Sidi Ali, Jaouda, Centrale Danone y figurent avec photo
et valeurs nutritionnelles. Aucune clé, aucun quota.

La couverture n'est pas totale — sur un échantillon de produits marocains,
deux références sur cinq manquaient. L'absence est donc un cas normal, pas
une erreur : l'appelant doit savoir proposer une saisie manuelle.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

log = logging.getLogger(__name__)

BASE = "https://world.openfoodfacts.org/api/v2/product"

# L'API demande un agent identifiable ; un agent générique est rejeté ou bridé.
AGENT = "PrixMaroc/1.0 (https://github.com/MOUBRAHIM/prixmaroc)"

CHAMPS = (
    "product_name,product_name_fr,brands,quantity,image_front_url,"
    "nutriments,nutriscore_grade,categories_tags"
)

DELAI = 12.0


@dataclass(frozen=True)
class FicheProduit:
    code: str
    nom: str
    marque: str | None
    format: str | None
    photo: str | None
    calories: float | None
    proteines: float | None
    lipides: float | None
    glucides: float | None
    fibres: float | None
    nutriscore: str | None


def _nombre(valeur: object) -> float | None:
    """Les nutriments arrivent tantôt en nombre, tantôt en chaîne, tantôt vides."""
    if valeur in (None, ""):
        return None
    try:
        n = float(valeur)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    # Une valeur négative ou délirante vient d'une saisie collaborative erronée.
    return n if 0 <= n <= 1000 else None


def _nom_lisible(p: dict) -> str:
    """Le nom français quand il existe : « سيدي علي » n'aide pas l'utilisateur."""
    for cle in ("product_name_fr", "product_name"):
        v = (p.get(cle) or "").strip()
        if v:
            return v[:200]
    return ""


async def chercher(code: str, client: httpx.AsyncClient | None = None) -> FicheProduit | None:
    """
    Fiche correspondant au code-barres, ou None si la référence est inconnue.

    Une panne réseau renvoie None comme une absence : du point de vue de
    l'utilisateur, les deux mènent à la même suite — saisir le produit
    à la main. L'incident est journalisé pour le diagnostic.
    """
    code = "".join(c for c in code if c.isdigit())
    if not 8 <= len(code) <= 14:
        return None

    url = f"{BASE}/{code}.json"
    entetes = {"User-Agent": AGENT}

    try:
        if client is None:
            async with httpx.AsyncClient(timeout=DELAI) as c:
                r = await c.get(url, params={"fields": CHAMPS}, headers=entetes)
        else:
            r = await client.get(url, params={"fields": CHAMPS}, headers=entetes)
        r.raise_for_status()
        donnees = r.json()
    except Exception as e:
        log.warning("Open Food Facts indisponible pour %s : %s", code, type(e).__name__)
        return None

    if donnees.get("status") != 1:
        return None

    p = donnees.get("product") or {}
    nom = _nom_lisible(p)
    if not nom:
        return None          # une fiche sans nom n'est pas exploitable

    n = p.get("nutriments") or {}
    score = (p.get("nutriscore_grade") or "").upper()

    return FicheProduit(
        code=code,
        nom=nom,
        marque=((p.get("brands") or "").split(",")[0].strip() or None),
        format=((p.get("quantity") or "").strip() or None),
        photo=(p.get("image_front_url") or None),
        calories=_nombre(n.get("energy-kcal_100g")),
        proteines=_nombre(n.get("proteins_100g")),
        lipides=_nombre(n.get("fat_100g")),
        glucides=_nombre(n.get("carbohydrates_100g")),
        fibres=_nombre(n.get("fiber_100g")),
        nutriscore=score if score in ("A", "B", "C", "D", "E") else None,
    )
