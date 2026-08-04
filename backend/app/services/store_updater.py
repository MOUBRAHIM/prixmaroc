"""
Service de mise à jour automatique des magasins.

Interroge OpenStreetMap (Overpass API) + store locators officiels
puis upserte les résultats en base de données.
Conçu pour être appelé depuis le scheduler APScheduler (job hebdomadaire)
ou depuis un endpoint admin (déclenchement manuel).

Architecture :
  fetch_all_stores()   → collecte depuis toutes les sources
  deduplicate()        → élimination des doublons par distance Haversine (150m)
  upsert_stores()      → insert / update en base (slug unique)
  run_update()         → point d'entrée complet, retourne un dict résumé
"""
from __future__ import annotations

import asyncio
import logging
import math
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Optional

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import AsyncSessionLocal
from app.models.store import Store

logger = logging.getLogger("prixmaroc.store_updater")

# ──────────────────────────────────────────────────────────────────────────────
# Chaînes connues
# ──────────────────────────────────────────────────────────────────────────────

CHAIN_META: dict[str, dict] = {
    "marjane":   {"name_prefix": "Marjane",   "website": "https://www.marjane.ma"},
    "carrefour": {"name_prefix": "Carrefour", "website": "https://www.carrefour.ma"},
    "labelvie":  {"name_prefix": "Label'Vie", "website": "https://www.labelvie.ma"},
    "bim":       {"name_prefix": "BIM",       "website": "https://www.bim.com.tr"},
    "acima":     {"name_prefix": "Acima",     "website": "https://www.acima.ma"},
    "atacadao":  {"name_prefix": "Atacadão",  "website": "https://www.atacadao.ma"},
    "kazyon":    {"name_prefix": "Kazyon",    "website": "https://www.kazyon.com"},
    "sopreco":   {"name_prefix": "Sopreco",   "website": "https://www.sopreco.ma"},
}

CHAIN_PATTERNS: list[tuple[str, str]] = [
    (r"marjane",          "marjane"),
    (r"carrefour",        "carrefour"),
    (r"label\s*'?\s*vie", "labelvie"),
    (r"\bbim\b",          "bim"),
    (r"acima",            "acima"),
    (r"atacad[aã]o",      "atacadao"),
    (r"kazyon",           "kazyon"),
    (r"sopreco",          "sopreco"),
]


def _detect_chain(name: str) -> Optional[str]:
    n = name.lower().strip()
    for pattern, chain in CHAIN_PATTERNS:
        if re.search(pattern, n):
            return chain
    return None


def _slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text.lower())
    return re.sub(r"[-\s]+", "-", text).strip("-")


# ──────────────────────────────────────────────────────────────────────────────
# Modèle interne
# ──────────────────────────────────────────────────────────────────────────────

@dataclass
class StoreData:
    name: str
    city: str
    address: str
    latitude: float
    longitude: float
    region: str = ""
    website: str = ""
    chain: str = ""
    source: str = "updater"


# ──────────────────────────────────────────────────────────────────────────────
# SOURCE 1 : OpenStreetMap Overpass API
# ──────────────────────────────────────────────────────────────────────────────

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

OSM_QUERY = """
[out:json][timeout:120];
(
  node["shop"~"supermarket|hypermarket|wholesale"](21.0,-17.5,36.0,-0.9);
  way["shop"~"supermarket|hypermarket|wholesale"](21.0,-17.5,36.0,-0.9);
  node["brand"~"Marjane|Carrefour|BIM|Label.Vie|Acima|Atacadao|Kazyon|Sopreco",i](21.0,-17.5,36.0,-0.9);
  way["brand"~"Marjane|Carrefour|BIM|Label.Vie|Acima|Atacadao|Kazyon|Sopreco",i](21.0,-17.5,36.0,-0.9);
  node["name"~"Marjane|Carrefour|BIM|Label.Vie|Acima|Atacadao|Kazyon|Sopreco",i](21.0,-17.5,36.0,-0.9);
  way["name"~"Marjane|Carrefour|BIM|Label.Vie|Acima|Atacadao|Kazyon|Sopreco",i](21.0,-17.5,36.0,-0.9);
);
out center tags;
"""


async def _fetch_osm_stores() -> list[StoreData]:
    """Interroge Overpass API et retourne les magasins GMS trouvés."""
    logger.info("[StoreUpdater] Requête Overpass API (OSM)…")
    stores: list[StoreData] = []
    try:
        async with httpx.AsyncClient(timeout=150.0) as client:
            resp = await client.post(OVERPASS_URL, data={"data": OSM_QUERY})
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(f"[StoreUpdater] Overpass indisponible : {exc}")
        return []

    elements = data.get("elements", [])
    logger.info(f"[StoreUpdater] OSM : {len(elements)} éléments bruts")

    for el in elements:
        tags = el.get("tags", {})
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lon = el.get("lon") or (el.get("center") or {}).get("lon")
        if not lat or not lon:
            continue

        name = (tags.get("name") or tags.get("brand") or tags.get("operator") or "").strip()
        if not name:
            continue

        chain = _detect_chain(name)
        brand = (tags.get("brand") or "").lower()
        for pattern, c in CHAIN_PATTERNS:
            if re.search(pattern, brand):
                chain = c
                break
        if not chain:
            continue

        addr_parts = [
            tags.get("addr:housenumber", ""),
            tags.get("addr:street", ""),
            tags.get("addr:suburb", ""),
        ]
        address = ", ".join(p for p in addr_parts if p).strip() or tags.get("addr:full", "")

        city = (
            tags.get("addr:city")
            or tags.get("addr:town")
            or tags.get("addr:village")
            or ""
        ).strip()
        if not city:
            continue

        meta = CHAIN_META.get(chain, {})
        stores.append(StoreData(
            name=name,
            city=city,
            address=address or f"{city}, Maroc",
            latitude=float(lat),
            longitude=float(lon),
            website=meta.get("website", ""),
            chain=chain,
            source="osm",
        ))

    logger.info(f"[StoreUpdater] OSM : {len(stores)} magasins GMS retenus")
    return stores


# ──────────────────────────────────────────────────────────────────────────────
# SOURCE 2 : Store locators officiels (Marjane, Label'Vie)
# ──────────────────────────────────────────────────────────────────────────────

async def _fetch_marjane_stores() -> list[StoreData]:
    endpoints = [
        "https://www.marjane.ma/api/stores",
        "https://www.marjane.ma/stores.json",
        "https://marjane.ma/nos-magasins/stores.json",
    ]
    async with httpx.AsyncClient(timeout=20.0) as client:
        for url in endpoints:
            try:
                resp = await client.get(url, headers={"User-Agent": "PrixMaroc/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    stores: list[StoreData] = []
                    items = data if isinstance(data, list) else data.get("stores", data.get("data", []))
                    for s in items:
                        lat = s.get("lat") or s.get("latitude") or s.get("gps_lat")
                        lng = s.get("lng") or s.get("longitude") or s.get("gps_lng")
                        name = s.get("name") or s.get("title") or ""
                        city = s.get("city") or s.get("ville") or ""
                        if lat and lng and city:
                            stores.append(StoreData(
                                name=name or f"Marjane {city}",
                                city=city,
                                address=s.get("address") or s.get("adresse") or f"{city}, Maroc",
                                latitude=float(lat),
                                longitude=float(lng),
                                website="https://www.marjane.ma",
                                chain="marjane",
                                source="locator",
                            ))
                    if stores:
                        logger.info(f"[StoreUpdater] Marjane locator : {len(stores)} magasins")
                        return stores
            except Exception:
                continue
    return []


async def _fetch_labelvie_stores() -> list[StoreData]:
    endpoints = [
        "https://www.labelvie.ma/api/stores",
        "https://www.labelvie.ma/magasins.json",
    ]
    async with httpx.AsyncClient(timeout=20.0) as client:
        for url in endpoints:
            try:
                resp = await client.get(url, headers={"User-Agent": "PrixMaroc/1.0"})
                if resp.status_code == 200:
                    data = resp.json()
                    stores: list[StoreData] = []
                    items = data if isinstance(data, list) else data.get("stores", data.get("data", []))
                    for s in items:
                        lat = s.get("lat") or s.get("latitude")
                        lng = s.get("lng") or s.get("longitude")
                        city = s.get("city") or s.get("ville") or ""
                        if lat and lng and city:
                            stores.append(StoreData(
                                name=s.get("name") or f"Label'Vie {city}",
                                city=city,
                                address=s.get("address") or f"{city}, Maroc",
                                latitude=float(lat),
                                longitude=float(lng),
                                website="https://www.labelvie.ma",
                                chain="labelvie",
                                source="locator",
                            ))
                    if stores:
                        logger.info(f"[StoreUpdater] Label'Vie locator : {len(stores)} magasins")
                        return stores
            except Exception:
                continue
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Déduplication Haversine
# ──────────────────────────────────────────────────────────────────────────────

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _deduplicate(stores: list[StoreData], radius_km: float = 0.15) -> list[StoreData]:
    """Élimine les doublons par chaîne + distance < radius_km."""
    unique: list[StoreData] = []
    for s in stores:
        is_dup = False
        for u in unique:
            if u.chain != s.chain:
                continue
            if _haversine_km(s.latitude, s.longitude, u.latitude, u.longitude) < radius_km:
                is_dup = True
                break
        if not is_dup:
            unique.append(s)
    return unique


# ──────────────────────────────────────────────────────────────────────────────
# Upsert en base
# ──────────────────────────────────────────────────────────────────────────────

async def _upsert_stores(
    db: AsyncSession,
    stores: list[StoreData],
) -> dict[str, int]:
    """Insère ou met à jour les magasins. Retourne {inserted, updated, skipped}."""
    stats = {"inserted": 0, "updated": 0, "skipped": 0}

    # Charger les slugs existants
    result = await db.execute(select(Store.slug))
    existing_slugs: set[str] = {row[0] for row in result.fetchall()}

    for s in stores:
        # Construire le slug candidat
        chain_prefix = CHAIN_META.get(s.chain, {}).get("name_prefix", s.name.split()[0])
        slug_base = _slugify(f"{chain_prefix}-{s.city}")
        slug = slug_base
        suffix = 2
        while slug in existing_slugs:
            # Vérifier si c'est déjà CE magasin (par coordonnées proches)
            res2 = await db.execute(select(Store).where(Store.slug == slug))
            existing = res2.scalar_one_or_none()
            if existing and existing.latitude and existing.longitude:
                dist = _haversine_km(s.latitude, s.longitude, existing.latitude, existing.longitude)
                if dist < 0.15:
                    # Même magasin → update si les données OSM sont plus récentes
                    existing.address = s.address or existing.address
                    existing.city = s.city or existing.city
                    existing.latitude = s.latitude
                    existing.longitude = s.longitude
                    existing.is_active = True
                    stats["updated"] += 1
                    break
            slug = f"{slug_base}-{suffix}"
            suffix += 1
        else:
            # Nouveau slug → insert
            meta = CHAIN_META.get(s.chain, {})
            store = Store(
                name=s.name,
                slug=slug,
                address=s.address,
                city=s.city,
                region=s.region or None,
                latitude=s.latitude,
                longitude=s.longitude,
                website=s.website or meta.get("website"),
                is_active=True,
            )
            db.add(store)
            existing_slugs.add(slug)
            stats["inserted"] += 1

    await db.commit()
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# Point d'entrée public
# ──────────────────────────────────────────────────────────────────────────────

async def run_update(
    sources: list[str] | None = None,
) -> dict:
    """
    Lance la mise à jour complète des magasins.

    Args:
        sources: liste de sources à utiliser. None ou ["all"] = toutes.
                 Valeurs possibles : "osm", "locator".

    Returns:
        dict avec clés : fetched, after_dedup, inserted, updated, sources_ok, sources_failed
    """
    if sources is None or sources == ["all"]:
        sources = ["osm", "locator"]

    all_stores: list[StoreData] = []
    sources_ok: list[str] = []
    sources_failed: list[str] = []

    # Collecte parallèle de toutes les sources
    tasks: list[tuple[str, asyncio.Task]] = []

    if "osm" in sources:
        tasks.append(("osm", asyncio.create_task(_fetch_osm_stores())))
    if "locator" in sources:
        tasks.append(("marjane_locator", asyncio.create_task(_fetch_marjane_stores())))
        tasks.append(("labelvie_locator", asyncio.create_task(_fetch_labelvie_stores())))

    for name, task in tasks:
        try:
            result = await task
            all_stores.extend(result)
            if result:
                sources_ok.append(name)
            else:
                sources_failed.append(f"{name} (0 résultats)")
        except Exception as exc:
            logger.warning(f"[StoreUpdater] Source '{name}' échouée : {exc}")
            sources_failed.append(name)

    logger.info(f"[StoreUpdater] Total brut : {len(all_stores)} magasins")

    if not all_stores:
        logger.warning("[StoreUpdater] Aucun magasin collecté — abandon")
        return {
            "fetched": 0,
            "after_dedup": 0,
            "inserted": 0,
            "updated": 0,
            "sources_ok": sources_ok,
            "sources_failed": sources_failed,
            "warning": "Aucun magasin collecté depuis les sources externes",
        }

    # Déduplication
    deduped = _deduplicate(all_stores, radius_km=0.15)
    logger.info(f"[StoreUpdater] Après déduplication : {len(deduped)} magasins")

    # Upsert en base
    async with AsyncSessionLocal() as db:
        stats = await _upsert_stores(db, deduped)

    logger.info(
        f"[StoreUpdater] Résultat : "
        f"{stats['inserted']} insérés, {stats['updated']} mis à jour, "
        f"{stats['skipped']} ignorés"
    )

    return {
        "fetched": len(all_stores),
        "after_dedup": len(deduped),
        "inserted": stats["inserted"],
        "updated": stats["updated"],
        "skipped": stats["skipped"],
        "sources_ok": sources_ok,
        "sources_failed": sources_failed,
    }
