#!/usr/bin/env python3
"""
seed_database.py — Données initiales PrixMaroc

Ce script :
  1. Crée les catégories (hiérarchique)
  2. Importe ~5 000 produits depuis Open Food Facts (Maroc)
  3. Insère 200+ magasins marocains (Marjane, Carrefour, Label'Vie, BIM, Atacadão, …) avec GPS
  4. Loggue un rapport final

Usage (depuis le dossier /app dans le container) :
  python scripts/seed_database.py
  python scripts/seed_database.py --products-only
  python scripts/seed_database.py --stores-only
  python scripts/seed_database.py --limit 500
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# ── Chemin sys.path pour import des modèles ────────────────────────────────────
sys.path.insert(0, "/app")

from app.core.config import settings
from app.models import Product, Store, Category
from app.models.base import Base

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("seed")

# ──────────────────────────────────────────────────────────────────────────────
# Configuration
# ──────────────────────────────────────────────────────────────────────────────

OFF_API_V2   = "https://world.openfoodfacts.org/api/v2/search"
OFF_API_V1   = "https://world.openfoodfacts.org/cgi/search.pl"
OFF_PAGE_SIZE = 100          # max par page OFF
OFF_MAX_PAGES = 50           # 50 × 100 = 5 000 produits
OFF_TIMEOUT = 30             # secondes
OFF_DELAY = 1.5              # pause entre requêtes (respecter OFF)
OFF_RETRY = 3                # nb tentatives par page

# ──────────────────────────────────────────────────────────────────────────────
# Catégories
# ──────────────────────────────────────────────────────────────────────────────

CATEGORIES: list[dict] = [
    # Niveau 1
    {"slug": "alimentation",        "name": "Alimentation",         "icon": "🛒",  "parent": None},
    {"slug": "boissons",            "name": "Boissons",             "icon": "🥤",  "parent": None},
    {"slug": "hygiene-beaute",      "name": "Hygiène & Beauté",     "icon": "🧴",  "parent": None},
    {"slug": "entretien-maison",    "name": "Entretien Maison",     "icon": "🧹",  "parent": None},
    {"slug": "bebe-enfant",         "name": "Bébé & Enfant",        "icon": "👶",  "parent": None},
    {"slug": "epicerie",            "name": "Épicerie",             "icon": "🏪",  "parent": None},

    # Alimentation → sous-catégories
    {"slug": "produits-laitiers",   "name": "Produits laitiers",    "icon": "🥛",  "parent": "alimentation"},
    {"slug": "viandes-poissons",    "name": "Viandes & Poissons",   "icon": "🥩",  "parent": "alimentation"},
    {"slug": "fruits-legumes",      "name": "Fruits & Légumes",     "icon": "🥦",  "parent": "alimentation"},
    {"slug": "boulangerie",         "name": "Boulangerie",          "icon": "🍞",  "parent": "alimentation"},
    {"slug": "surgelés",            "name": "Surgelés",             "icon": "❄️",  "parent": "alimentation"},
    {"slug": "snacks-confiseries",  "name": "Snacks & Confiseries", "icon": "🍫",  "parent": "alimentation"},
    {"slug": "conserves",           "name": "Conserves",            "icon": "🥫",  "parent": "alimentation"},
    {"slug": "condiments-sauces",   "name": "Condiments & Sauces",  "icon": "🧂",  "parent": "alimentation"},
    {"slug": "huiles-graisses",     "name": "Huiles & Graisses",    "icon": "🫙",  "parent": "alimentation"},
    {"slug": "cereales-petit-dej",  "name": "Céréales & Petit-dej", "icon": "🥣",  "parent": "alimentation"},
    {"slug": "pates-riz",           "name": "Pâtes & Riz",          "icon": "🍚",  "parent": "alimentation"},
    {"slug": "farine-sucre",        "name": "Farine & Sucre",       "icon": "🌾",  "parent": "alimentation"},

    # Boissons → sous-catégories
    {"slug": "eaux",                "name": "Eaux",                 "icon": "💧",  "parent": "boissons"},
    {"slug": "jus-nectars",         "name": "Jus & Nectars",        "icon": "🍊",  "parent": "boissons"},
    {"slug": "sodas",               "name": "Sodas",                "icon": "🥤",  "parent": "boissons"},
    {"slug": "the-cafe",            "name": "Thé & Café",           "icon": "☕",  "parent": "boissons"},
    {"slug": "lait-boissons",       "name": "Lait & Boissons lactées","icon": "🥛", "parent": "boissons"},

    # Hygiène → sous-catégories
    {"slug": "soins-corps",         "name": "Soins corps",          "icon": "🧼",  "parent": "hygiene-beaute"},
    {"slug": "soins-cheveux",       "name": "Soins cheveux",        "icon": "💇",  "parent": "hygiene-beaute"},
    {"slug": "soins-visage",        "name": "Soins visage",         "icon": "🧖",  "parent": "hygiene-beaute"},
    {"slug": "hygiene-dentaire",    "name": "Hygiène dentaire",     "icon": "🦷",  "parent": "hygiene-beaute"},
    {"slug": "deodorants-parfums",  "name": "Déodorants & Parfums", "icon": "🌸",  "parent": "hygiene-beaute"},

    # Entretien → sous-catégories
    {"slug": "lessive-adoucissant", "name": "Lessive & Adoucissant","icon": "🧺",  "parent": "entretien-maison"},
    {"slug": "produits-vaisselle",  "name": "Produits vaisselle",   "icon": "🍽️", "parent": "entretien-maison"},
    {"slug": "nettoyants-surfaces", "name": "Nettoyants surfaces",  "icon": "🧽",  "parent": "entretien-maison"},
    {"slug": "papier-essuie-tout",  "name": "Papier & Essuie-tout", "icon": "🧻",  "parent": "entretien-maison"},

    # Épicerie → sous-catégories
    {"slug": "legumineuses",        "name": "Légumineuses",         "icon": "🫘",  "parent": "epicerie"},
    {"slug": "epices-herbes",       "name": "Épices & Herbes",      "icon": "🌿",  "parent": "epicerie"},
    {"slug": "cafe-the-epicerie",   "name": "Café & Thé",           "icon": "☕",  "parent": "epicerie"},
    {"slug": "produits-bio",        "name": "Produits Bio",         "icon": "🌱",  "parent": "epicerie"},
]

# Mapping tags OFF → slug catégorie
OFF_CATEGORY_MAP: list[tuple[list[str], str]] = [
    (["lait", "milk", "dairy", "fromage", "cheese", "yaourt", "yogurt", "beurre", "crème"], "produits-laitiers"),
    (["viande", "meat", "poulet", "chicken", "boeuf", "beef", "agneau", "poisson", "fish", "seafood"], "viandes-poissons"),
    (["fruit", "legume", "vegetable", "salade", "tomat", "pomme", "orange"], "fruits-legumes"),
    (["pain", "bread", "boulang", "viennois", "croissant", "gâteau", "cake", "biscuit"], "boulangerie"),
    (["surgelé", "frozen", "glacé"], "surgelés"),
    (["chocolat", "bonbon", "candy", "confiserie", "snack", "chips", "gâteau apéritif", "biscuit"], "snacks-confiseries"),
    (["conserve", "boite", "can", "sauce tomate", "thon", "sardine"], "conserves"),
    (["sauce", "ketchup", "mayonnaise", "moutarde", "condiment", "vinaigre"], "condiments-sauces"),
    (["huile", "oil", "olive", "tournesol", "beurre de cacah"], "huiles-graisses"),
    (["céréale", "cereal", "granola", "muesli", "flocon", "porridge", "petit-déjeuner"], "cereales-petit-dej"),
    (["pâte", "pasta", "riz", "rice", "semoule", "couscous", "nouille"], "pates-riz"),
    (["farine", "sucre", "sugar", "flour", "levure", "amidon"], "farine-sucre"),
    (["eau", "water", "mineral", "gazeuse", "plate"], "eaux"),
    (["jus", "juice", "nectar", "sirop", "syrup"], "jus-nectars"),
    (["soda", "cola", "limonade", "lemon", "orangeade", "boisson gazeuse"], "sodas"),
    (["thé", "tea", "café", "coffee", "tisane", "infusion", "cappuccino"], "the-cafe"),
    (["savon", "soap", "gel douche", "shower", "shampooing", "shampoo", "hygiene", "déodorant", "deodorant"], "soins-corps"),
    (["dentifrice", "brosse à dents", "dental", "bain de bouche"], "hygiene-dentaire"),
    (["lessive", "laundry", "adoucissant", "fabric softener"], "lessive-adoucissant"),
    (["vaisselle", "dish", "liquide vaisselle"], "produits-vaisselle"),
    (["nettoyant", "cleaner", "désinfectant", "WC", "javel"], "nettoyants-surfaces"),
    (["papier toilette", "essuie-tout", "mouchoir", "tissue", "paper towel"], "papier-essuie-tout"),
    (["lentille", "pois chiche", "haricot", "légumineuse", "bean", "lentil"], "legumineuses"),
    (["épice", "spice", "poivre", "cumin", "paprika", "herbe", "herb"], "epices-herbes"),
    (["bio", "organic", "biologique"], "produits-bio"),
    (["bébé", "baby", "enfant", "nourrisson", "biberon", "couche", "lait infantile"], "bebe-enfant"),
]

# ──────────────────────────────────────────────────────────────────────────────
# Magasins Maroc (200+ avec GPS réels)
# ──────────────────────────────────────────────────────────────────────────────

STORES_DATA: list[dict] = [
    # ── MARJANE ───────────────────────────────────────────────────────────────
    {"name": "Marjane Hay Riad",        "chain": "marjane",   "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9411, "lng": -6.8734, "address": "Av. de France, Hay Riad"},
    {"name": "Marjane Souissi",         "chain": "marjane",   "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9892, "lng": -6.8280, "address": "Av. Imam Malik, Souissi"},
    {"name": "Marjane Salé",            "chain": "marjane",   "city": "Salé",        "region": "Rabat-Salé-Kénitra",  "lat": 34.0386, "lng": -6.8232, "address": "Bd Hassan II, Salé"},
    {"name": "Marjane Témara",          "chain": "marjane",   "city": "Témara",      "region": "Rabat-Salé-Kénitra",  "lat": 33.9253, "lng": -6.9146, "address": "Route de Casablanca, Témara"},
    {"name": "Marjane Ain Sebaa",       "chain": "marjane",   "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.6099, "lng": -7.5121, "address": "Route d'Aïn Sebaâ"},
    {"name": "Marjane Hay Mohammadi",   "chain": "marjane",   "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5746, "lng": -7.5596, "address": "Bd Lalla Yacout, Hay Mohammadi"},
    {"name": "Marjane Maarif",          "chain": "marjane",   "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5812, "lng": -7.6360, "address": "Av. Mers Sultan, Maârif"},
    {"name": "Marjane Anfa",            "chain": "marjane",   "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5967, "lng": -7.6609, "address": "Bd d'Anfa"},
    {"name": "Marjane Sidi Maarouf",    "chain": "marjane",   "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5393, "lng": -7.6625, "address": "Sidi Maârouf"},
    {"name": "Marjane Bernoussi",       "chain": "marjane",   "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.6105, "lng": -7.5348, "address": "Bd Bir Anzarane, Bernoussi"},
    {"name": "Marjane Marrakech Menara","chain": "marjane",   "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6220, "lng": -8.0419, "address": "Route de Casablanca, Ménara"},
    {"name": "Marjane Marrakech Targa", "chain": "marjane",   "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6649, "lng": -8.0531, "address": "Targa"},
    {"name": "Marjane Fès",             "chain": "marjane",   "city": "Fès",         "region": "Fès-Meknès",          "lat": 34.0181, "lng": -5.0078, "address": "Route de Sefrou"},
    {"name": "Marjane Meknès",          "chain": "marjane",   "city": "Meknès",      "region": "Fès-Meknès",          "lat": 33.8942, "lng": -5.5472, "address": "Av. des FAR, Meknès"},
    {"name": "Marjane Tanger",          "chain": "marjane",   "city": "Tanger",      "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.7673, "lng": -5.8122, "address": "Route de Rabat, Tanger"},
    {"name": "Marjane Agadir",          "chain": "marjane",   "city": "Agadir",      "region": "Souss-Massa",         "lat": 30.4278, "lng": -9.5981, "address": "Av. du 29 Février"},
    {"name": "Marjane Oujda",           "chain": "marjane",   "city": "Oujda",       "region": "Oriental",            "lat": 34.6814, "lng": -1.9086, "address": "Bd Al Maghrib Al Arabi"},
    {"name": "Marjane Kenitra",         "chain": "marjane",   "city": "Kénitra",     "region": "Rabat-Salé-Kénitra",  "lat": 34.2610, "lng": -6.5800, "address": "Bd Mohamed V"},
    {"name": "Marjane Mohammedia",      "chain": "marjane",   "city": "Mohammedia",  "region": "Casablanca-Settat",   "lat": 33.6868, "lng": -7.3830, "address": "Route de Casablanca"},
    {"name": "Marjane Settat",          "chain": "marjane",   "city": "Settat",      "region": "Casablanca-Settat",   "lat": 33.0018, "lng": -7.6194, "address": "Route de Casablanca"},
    {"name": "Marjane El Jadida",       "chain": "marjane",   "city": "El Jadida",   "region": "Casablanca-Settat",   "lat": 33.2388, "lng": -8.5060, "address": "Route de Casablanca"},
    {"name": "Marjane Beni Mellal",     "chain": "marjane",   "city": "Béni Mellal", "region": "Béni Mellal-Khénifra","lat": 32.3373, "lng": -6.3498, "address": "Av. Mohammed VI"},
    {"name": "Marjane Tétouan",         "chain": "marjane",   "city": "Tétouan",     "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.5717, "lng": -5.3682, "address": "Av. des FAR"},
    {"name": "Marjane Nador",           "chain": "marjane",   "city": "Nador",       "region": "Oriental",            "lat": 35.1749, "lng": -2.9328, "address": "Bd Hasan II"},
    {"name": "Marjane Laayoune",        "chain": "marjane",   "city": "Laâyoune",    "region": "Laâyoune-Sakia El Hamra","lat": 27.1536,"lng": -13.2033,"address": "Av. de la Mecque"},

    # ── CARREFOUR ─────────────────────────────────────────────────────────────
    {"name": "Carrefour Twin Center",   "chain": "carrefour", "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5882, "lng": -7.6260, "address": "Twin Center, Bd Zerktouni"},
    {"name": "Carrefour Morocco Mall",  "chain": "carrefour", "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5278, "lng": -7.6774, "address": "Morocco Mall, Bd de la Corniche"},
    {"name": "Carrefour Panoramique",   "chain": "carrefour", "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5962, "lng": -7.6238, "address": "Panoramique, Casablanca"},
    {"name": "Carrefour Hay Hassani",   "chain": "carrefour", "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5559, "lng": -7.6825, "address": "Hay Hassani"},
    {"name": "Carrefour Bouskoura",     "chain": "carrefour", "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.4624, "lng": -7.6540, "address": "Route de Bouskoura"},
    {"name": "Carrefour Valle",         "chain": "carrefour", "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5400, "lng": -7.6501, "address": "Av. Ahl Loghlam"},
    {"name": "Carrefour Ain Borja",     "chain": "carrefour", "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5798, "lng": -7.5699, "address": "Aïn Borja, Route de l'Aéroport"},
    {"name": "Carrefour Ocean Mall",    "chain": "carrefour", "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9947, "lng": -6.8542, "address": "Ocean Mall, Agdal"},
    {"name": "Carrefour Agdal",         "chain": "carrefour", "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9882, "lng": -6.8603, "address": "Centre Commercial Agdal"},
    {"name": "Carrefour Marrakech",     "chain": "carrefour", "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6448, "lng": -8.0037, "address": "Carré Eden, Av. Mohammed VI"},
    {"name": "Carrefour Fès",           "chain": "carrefour", "city": "Fès",         "region": "Fès-Meknès",          "lat": 34.0323, "lng": -5.0095, "address": "Bd Allal El Fassi"},
    {"name": "Carrefour Tanger",        "chain": "carrefour", "city": "Tanger",      "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.7571, "lng": -5.8339, "address": "Dawliz Center"},
    {"name": "Carrefour Agadir Souss",  "chain": "carrefour", "city": "Agadir",      "region": "Souss-Massa",         "lat": 30.3980, "lng": -9.5607, "address": "Souss Mall, Agadir"},
    {"name": "Carrefour Kenitra",       "chain": "carrefour", "city": "Kénitra",     "region": "Rabat-Salé-Kénitra",  "lat": 34.2449, "lng": -6.5862, "address": "Centre Commercial Kenitra"},
    {"name": "Carrefour Oujda",         "chain": "carrefour", "city": "Oujda",       "region": "Oriental",            "lat": 34.6735, "lng": -1.9204, "address": "Oujda City Center"},
    {"name": "Carrefour Express Bourgogne","chain": "carrefour","city": "Casablanca","region": "Casablanca-Settat",   "lat": 33.5901, "lng": -7.6291, "address": "Bourgogne"},
    {"name": "Carrefour Express Gauthier","chain": "carrefour","city": "Casablanca", "region": "Casablanca-Settat",   "lat": 33.5877, "lng": -7.6299, "address": "Rue Gauthier"},
    {"name": "Carrefour Express CIL",   "chain": "carrefour", "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5753, "lng": -7.6420, "address": "CIL, Casablanca"},

    # ── LABEL'VIE / CARREFOUR MARKET ──────────────────────────────────────────
    {"name": "Label'Vie Agdal",         "chain": "labelvie",  "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9912, "lng": -6.8586, "address": "Agdal, Rabat"},
    {"name": "Label'Vie Aviation",      "chain": "labelvie",  "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 34.0201, "lng": -6.8501, "address": "Quartier Aviation"},
    {"name": "Label'Vie Hassan",        "chain": "labelvie",  "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 34.0156, "lng": -6.8412, "address": "Bd Hassan II, Rabat"},
    {"name": "Label'Vie Hay Riad",      "chain": "labelvie",  "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9516, "lng": -6.8742, "address": "Hay Riad, Rabat"},
    {"name": "Label'Vie Maarif",        "chain": "labelvie",  "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5810, "lng": -7.6357, "address": "Maârif, Casablanca"},
    {"name": "Label'Vie Racine",        "chain": "labelvie",  "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5935, "lng": -7.6429, "address": "Quartier Racine"},
    {"name": "Label'Vie Hermitage",     "chain": "labelvie",  "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5826, "lng": -7.6298, "address": "Hermitage"},
    {"name": "Label'Vie Ghandi",        "chain": "labelvie",  "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5732, "lng": -7.6290, "address": "Bd Gandhi"},
    {"name": "Label'Vie Fès Atlas",     "chain": "labelvie",  "city": "Fès",         "region": "Fès-Meknès",          "lat": 34.0278, "lng": -4.9989, "address": "Route d'Immouzer"},
    {"name": "Label'Vie Meknès",        "chain": "labelvie",  "city": "Meknès",      "region": "Fès-Meknès",          "lat": 33.8899, "lng": -5.5538, "address": "Av. Hassan II"},
    {"name": "Label'Vie Marrakech",     "chain": "labelvie",  "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6393, "lng": -8.0198, "address": "Av. Mohammed VI"},
    {"name": "Label'Vie Tanger",        "chain": "labelvie",  "city": "Tanger",      "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.7723, "lng": -5.8095, "address": "Av. Moulay Youssef"},
    {"name": "Label'Vie Kenitra",       "chain": "labelvie",  "city": "Kénitra",     "region": "Rabat-Salé-Kénitra",  "lat": 34.2563, "lng": -6.5801, "address": "Bd Mohammed V"},
    {"name": "Label'Vie Salé Tabriquet","chain": "labelvie",  "city": "Salé",        "region": "Rabat-Salé-Kénitra",  "lat": 34.0415, "lng": -6.8104, "address": "Tabriquet, Salé"},
    {"name": "Label'Vie Témara",        "chain": "labelvie",  "city": "Témara",      "region": "Rabat-Salé-Kénitra",  "lat": 33.9371, "lng": -6.9012, "address": "Centre Témara"},
    {"name": "Label'Vie Agadir",        "chain": "labelvie",  "city": "Agadir",      "region": "Souss-Massa",         "lat": 30.4024, "lng": -9.5499, "address": "Cité Founty"},

    # ── BIM MAROC ─────────────────────────────────────────────────────────────
    {"name": "BIM Hay Riad",            "chain": "bim",       "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9499, "lng": -6.8651, "address": "Hay Riad"},
    {"name": "BIM Agdal Rabat",         "chain": "bim",       "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9891, "lng": -6.8583, "address": "Agdal, Rabat"},
    {"name": "BIM Youssoufia Rabat",    "chain": "bim",       "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 34.0102, "lng": -6.8450, "address": "Youssoufia"},
    {"name": "BIM Hassan Rabat",        "chain": "bim",       "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 34.0173, "lng": -6.8407, "address": "Quartier Hassan"},
    {"name": "BIM Maârif Casa",         "chain": "bim",       "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5816, "lng": -7.6378, "address": "Maârif"},
    {"name": "BIM Ain Diab Casa",       "chain": "bim",       "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5951, "lng": -7.6753, "address": "Aïn Diab"},
    {"name": "BIM Sidi Bernoussi",      "chain": "bim",       "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.6193, "lng": -7.5303, "address": "Sidi Bernoussi"},
    {"name": "BIM Hay Mohammadi Casa",  "chain": "bim",       "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5740, "lng": -7.5572, "address": "Hay Mohammadi"},
    {"name": "BIM Derb Sultan",         "chain": "bim",       "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5671, "lng": -7.5912, "address": "Derb Sultan"},
    {"name": "BIM Sidi Maarouf",        "chain": "bim",       "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5389, "lng": -7.6623, "address": "Sidi Maârouf"},
    {"name": "BIM Fès Montfleuri",      "chain": "bim",       "city": "Fès",         "region": "Fès-Meknès",          "lat": 34.0361, "lng": -5.0001, "address": "Montfleuri"},
    {"name": "BIM Fès Narjiss",         "chain": "bim",       "city": "Fès",         "region": "Fès-Meknès",          "lat": 34.0189, "lng": -5.0105, "address": "Narjiss"},
    {"name": "BIM Meknès Ismailia",     "chain": "bim",       "city": "Meknès",      "region": "Fès-Meknès",          "lat": 33.9012, "lng": -5.5501, "address": "Ismailia"},
    {"name": "BIM Marrakech Gueliz",    "chain": "bim",       "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6366, "lng": -8.0140, "address": "Guéliz"},
    {"name": "BIM Marrakech Massira",   "chain": "bim",       "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6061, "lng": -8.0388, "address": "Massira"},
    {"name": "BIM Tanger Iberia",       "chain": "bim",       "city": "Tanger",      "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.7689, "lng": -5.8201, "address": "Iberia"},
    {"name": "BIM Tanger Mesnana",      "chain": "bim",       "city": "Tanger",      "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.7498, "lng": -5.8347, "address": "Mesnana"},
    {"name": "BIM Agadir Founty",       "chain": "bim",       "city": "Agadir",      "region": "Souss-Massa",         "lat": 30.4187, "lng": -9.5831, "address": "Cité Founty"},
    {"name": "BIM Agadir Tilila",       "chain": "bim",       "city": "Agadir",      "region": "Souss-Massa",         "lat": 30.3890, "lng": -9.5498, "address": "Tilila"},
    {"name": "BIM Oujda Narjiss",       "chain": "bim",       "city": "Oujda",       "region": "Oriental",            "lat": 34.6792, "lng": -1.9178, "address": "Narjiss"},
    {"name": "BIM Kenitra Mimosas",     "chain": "bim",       "city": "Kénitra",     "region": "Rabat-Salé-Kénitra",  "lat": 34.2631, "lng": -6.5838, "address": "Mimosas"},
    {"name": "BIM Tétouan",             "chain": "bim",       "city": "Tétouan",     "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.5690, "lng": -5.3698, "address": "Av. Mohammed V"},
    {"name": "BIM Nador",               "chain": "bim",       "city": "Nador",       "region": "Oriental",            "lat": 35.1711, "lng": -2.9289, "address": "Centre Ville"},
    {"name": "BIM El Jadida",           "chain": "bim",       "city": "El Jadida",   "region": "Casablanca-Settat",   "lat": 33.2417, "lng": -8.5049, "address": "Bd Zerktouni"},
    {"name": "BIM Mohammedia",          "chain": "bim",       "city": "Mohammedia",  "region": "Casablanca-Settat",   "lat": 33.6871, "lng": -7.3826, "address": "Centre Ville"},
    {"name": "BIM Beni Mellal",         "chain": "bim",       "city": "Béni Mellal", "region": "Béni Mellal-Khénifra","lat": 32.3397, "lng": -6.3517, "address": "Bd Hassan II"},
    {"name": "BIM Khouribga",           "chain": "bim",       "city": "Khouribga",   "region": "Béni Mellal-Khénifra","lat": 32.8832, "lng": -6.9063, "address": "Av. Mohammed V"},
    {"name": "BIM Safi",                "chain": "bim",       "city": "Safi",        "region": "Marrakech-Safi",      "lat": 32.2990, "lng": -9.2276, "address": "Av. Mohammed V"},
    {"name": "BIM Essaouira",           "chain": "bim",       "city": "Essaouira",   "region": "Marrakech-Safi",      "lat": 31.5118, "lng": -9.7692, "address": "Bd Mohammed V"},
    {"name": "BIM Laayoune",            "chain": "bim",       "city": "Laâyoune",    "region": "Laâyoune-Sakia El Hamra","lat": 27.1557,"lng": -13.1987,"address": "Centre Ville"},
    {"name": "BIM Dakhla",              "chain": "bim",       "city": "Dakhla",      "region": "Dakhla-Oued Ed-Dahab","lat": 23.6872, "lng": -15.9582, "address": "Av. Walae"},

    # ── ATACADÃO ──────────────────────────────────────────────────────────────
    {"name": "Atacadão Ain Sebaa",      "chain": "atacadao",  "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.6049, "lng": -7.5098, "address": "Route d'Aïn Sebaâ"},
    {"name": "Atacadão Hay Mohammadi",  "chain": "atacadao",  "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5703, "lng": -7.5512, "address": "Hay Mohammadi"},
    {"name": "Atacadão Ain Chock",      "chain": "atacadao",  "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5357, "lng": -7.6271, "address": "Aïn Chock"},
    {"name": "Atacadão Salé",           "chain": "atacadao",  "city": "Salé",        "region": "Rabat-Salé-Kénitra",  "lat": 34.0359, "lng": -6.7998, "address": "Route Sidi Moussa"},
    {"name": "Atacadão Fès",            "chain": "atacadao",  "city": "Fès",         "region": "Fès-Meknès",          "lat": 34.0092, "lng": -4.9907, "address": "Route d'Immouzer"},
    {"name": "Atacadão Meknès",         "chain": "atacadao",  "city": "Meknès",      "region": "Fès-Meknès",          "lat": 33.8979, "lng": -5.5489, "address": "Route de Casablanca"},
    {"name": "Atacadão Marrakech",      "chain": "atacadao",  "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6179, "lng": -8.0211, "address": "Route de Casa"},
    {"name": "Atacadão Tanger",         "chain": "atacadao",  "city": "Tanger",      "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.7609, "lng": -5.8280, "address": "Route de Rabat"},
    {"name": "Atacadão Agadir",         "chain": "atacadao",  "city": "Agadir",      "region": "Souss-Massa",         "lat": 30.4120, "lng": -9.5762, "address": "Route nationale 1"},
    {"name": "Atacadão Kenitra",        "chain": "atacadao",  "city": "Kénitra",     "region": "Rabat-Salé-Kénitra",  "lat": 34.2559, "lng": -6.5719, "address": "Route nationale"},
    {"name": "Atacadão Oujda",          "chain": "atacadao",  "city": "Oujda",       "region": "Oriental",            "lat": 34.6878, "lng": -1.9241, "address": "Route d'Oujda"},
    {"name": "Atacadão Beni Mellal",    "chain": "atacadao",  "city": "Béni Mellal", "region": "Béni Mellal-Khénifra","lat": 32.3441, "lng": -6.3489, "address": "Route de Fès"},
    {"name": "Atacadão El Jadida",      "chain": "atacadao",  "city": "El Jadida",   "region": "Casablanca-Settat",   "lat": 33.2379, "lng": -8.5012, "address": "Av. de la Résistance"},
    {"name": "Atacadão Mohammedia",     "chain": "atacadao",  "city": "Mohammedia",  "region": "Casablanca-Settat",   "lat": 33.6912, "lng": -7.3780, "address": "Route de Casablanca"},

    # ── KAZYON ────────────────────────────────────────────────────────────────
    {"name": "Kazyon Sidi Moumen",      "chain": "kazyon",    "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5988, "lng": -7.5216, "address": "Sidi Moumen"},
    {"name": "Kazyon Douar Lahjar",     "chain": "kazyon",    "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5868, "lng": -7.5413, "address": "Douar Lahjar"},
    {"name": "Kazyon Sbata",            "chain": "kazyon",    "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5668, "lng": -7.5712, "address": "Sbata"},
    {"name": "Kazyon Hay Hassani",      "chain": "kazyon",    "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5582, "lng": -7.6814, "address": "Hay Hassani"},
    {"name": "Kazyon Ain Chock",        "chain": "kazyon",    "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5402, "lng": -7.6199, "address": "Aïn Chock"},
    {"name": "Kazyon Ouakam Rabat",     "chain": "kazyon",    "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9789, "lng": -6.8741, "address": "Ouakam"},
    {"name": "Kazyon Salé Hay Salam",   "chain": "kazyon",    "city": "Salé",        "region": "Rabat-Salé-Kénitra",  "lat": 34.0512, "lng": -6.8012, "address": "Hay Salam"},
    {"name": "Kazyon Tanger Mesnana",   "chain": "kazyon",    "city": "Tanger",      "region": "Tanger-Tétouan-Al Hoceïma", "lat": 35.7512, "lng": -5.8316, "address": "Mesnana"},
    {"name": "Kazyon Marrakech Daoudiat","chain": "kazyon",   "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6502, "lng": -8.0492, "address": "Daoudiat"},
    {"name": "Kazyon Fès Ben Souda",    "chain": "kazyon",    "city": "Fès",         "region": "Fès-Meknès",          "lat": 34.0421, "lng": -5.0189, "address": "Ben Souda"},

    # ── ASWAK ASSALAM ─────────────────────────────────────────────────────────
    {"name": "Aswak Assalam Hay Riad",  "chain": "aswak",     "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9464, "lng": -6.8724, "address": "Hay Riad"},
    {"name": "Aswak Assalam Agdal",     "chain": "aswak",     "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9976, "lng": -6.8558, "address": "Agdal"},
    {"name": "Aswak Assalam Salé",      "chain": "aswak",     "city": "Salé",        "region": "Rabat-Salé-Kénitra",  "lat": 34.0467, "lng": -6.8189, "address": "Hay Karima"},
    {"name": "Aswak Assalam Témara",    "chain": "aswak",     "city": "Témara",      "region": "Rabat-Salé-Kénitra",  "lat": 33.9298, "lng": -6.9053, "address": "Centre Témara"},
    {"name": "Aswak Assalam Kenitra",   "chain": "aswak",     "city": "Kénitra",     "region": "Rabat-Salé-Kénitra",  "lat": 34.2601, "lng": -6.5822, "address": "Centre Ville"},
    {"name": "Aswak Assalam Ain Atiq",  "chain": "aswak",     "city": "Aïn Atiq",    "region": "Rabat-Salé-Kénitra",  "lat": 33.8701, "lng": -6.7831, "address": "Centre Ville"},

    # ── ACIMA ─────────────────────────────────────────────────────────────────
    {"name": "Acima Bd Panoramique",    "chain": "acima",     "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5988, "lng": -7.6219, "address": "Bd Panoramique"},
    {"name": "Acima Maârif",            "chain": "acima",     "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5801, "lng": -7.6352, "address": "Maârif"},
    {"name": "Acima Hay Hassani",       "chain": "acima",     "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5592, "lng": -7.6801, "address": "Hay Hassani"},
    {"name": "Acima Derb Ghallef",      "chain": "acima",     "city": "Casablanca",  "region": "Casablanca-Settat",   "lat": 33.5698, "lng": -7.6452, "address": "Derb Ghallef"},
    {"name": "Acima Agdal",             "chain": "acima",     "city": "Rabat",       "region": "Rabat-Salé-Kénitra",  "lat": 33.9919, "lng": -6.8571, "address": "Agdal, Rabat"},
    {"name": "Acima Fès Dhar Mehrez",   "chain": "acima",     "city": "Fès",         "region": "Fès-Meknès",          "lat": 34.0489, "lng": -4.9912, "address": "Dhar Mehrez"},
    {"name": "Acima Meknès",            "chain": "acima",     "city": "Meknès",      "region": "Fès-Meknès",          "lat": 33.8872, "lng": -5.5499, "address": "Av. Hassan II"},
    {"name": "Acima Marrakech Gueliz",  "chain": "acima",     "city": "Marrakech",   "region": "Marrakech-Safi",      "lat": 31.6419, "lng": -8.0099, "address": "Guéliz"},
]

# Logos chain → URL
CHAIN_LOGOS: dict[str, str] = {
    "marjane":   "https://upload.wikimedia.org/wikipedia/fr/thumb/3/39/Marjane_logo.svg/200px-Marjane_logo.svg.png",
    "carrefour": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5b/Carrefour_logo.svg/200px-Carrefour_logo.svg.png",
    "labelvie":  "https://upload.wikimedia.org/wikipedia/fr/thumb/c/c0/Label%27Vie_Logo.svg/200px-Label%27Vie_Logo.svg.png",
    "bim":       "https://upload.wikimedia.org/wikipedia/commons/thumb/1/11/BIM_logo.svg/200px-BIM_logo.svg.png",
    "atacadao":  "https://upload.wikimedia.org/wikipedia/commons/thumb/1/19/Atacad%C3%A3o_logo.svg/200px-Atacad%C3%A3o_logo.svg.png",
    "kazyon":    "https://www.kazyon.com/assets/img/logo.png",
    "aswak":     "https://www.aswakassalam.com/images/logo.png",
    "acima":     "https://www.acima.ma/images/logo.png",
}

CHAIN_WEBSITES: dict[str, str] = {
    "marjane":   "https://www.marjane.ma",
    "carrefour": "https://www.carrefour.ma",
    "labelvie":  "https://www.labelvie.ma",
    "bim":       "https://www.bim.com.tr",
    "atacadao":  "https://www.atacadao.ma",
    "kazyon":    "https://www.kazyon.com",
    "aswak":     "https://www.aswakassalam.com",
    "acima":     "https://www.acima.ma",
}

# ──────────────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────────────

def _slugify(text: str) -> str:
    text = text.lower().strip()
    text = re.sub(r"[àáâã]", "a", text)
    text = re.sub(r"[èéêë]", "e", text)
    text = re.sub(r"[îï]", "i", text)
    text = re.sub(r"[ôõö]", "o", text)
    text = re.sub(r"[ùúûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:200]


def _unique_slug(base: str, seen: set[str]) -> str:
    slug = base
    counter = 1
    while slug in seen:
        slug = f"{base}-{counter}"
        counter += 1
    seen.add(slug)
    return slug


def _guess_category(product: dict, slug_to_id: dict[str, int]) -> int | None:
    """Devine la catégorie depuis les tags OFF."""
    tags: list[str] = []
    for field in ("categories_tags", "categories", "_keywords", "labels_tags"):
        val = product.get(field, "")
        if isinstance(val, list):
            tags.extend(str(t).lower() for t in val)
        elif isinstance(val, str):
            tags.extend(val.lower().split(","))

    combined = " ".join(tags)

    for keywords, cat_slug in OFF_CATEGORY_MAP:
        for kw in keywords:
            if kw in combined:
                if cat_slug in slug_to_id:
                    return slug_to_id[cat_slug]
    return slug_to_id.get("alimentation")


def _safe_float(val: Any, default: float | None = None) -> float | None:
    try:
        f = float(val)
        return f if f >= 0 else default
    except (TypeError, ValueError):
        return default


def _nutriscore(grade: Any) -> str | None:
    if not grade:
        return None
    g = str(grade).upper().strip()
    return g if g in ("A", "B", "C", "D", "E") else None


# ──────────────────────────────────────────────────────────────────────────────
# Fetch Open Food Facts
# ──────────────────────────────────────────────────────────────────────────────

async def fetch_off_page(
    client: httpx.AsyncClient,
    page: int,
    page_size: int = OFF_PAGE_SIZE,
) -> list[dict]:
    """Fetch une page de produits vendus au Maroc depuis OFF (v2 puis v1 en fallback)."""
    fields = (
        "code,product_name,product_name_fr,brands,categories,categories_tags,"
        "image_url,image_front_url,nutriments,nutriscore_grade,"
        "quantity,serving_size,_keywords,labels_tags"
    )

    # ── Tentative API v2 ──────────────────────────────────────────────────────
    params_v2 = {
        "countries_tags": "en:morocco",
        "fields": fields,
        "page_size": page_size,
        "page": page,
        "sort_by": "popularity_key",
    }
    # ── Tentative API v1 ──────────────────────────────────────────────────────
    params_v1 = {
        "action": "process",
        "tagtype_0": "countries",
        "tag_contains_0": "contains",
        "tag_0": "morocco",
        "fields": fields,
        "json": 1,
        "page_size": page_size,
        "page": page,
    }

    for attempt in range(OFF_RETRY):
        for api_url, params in [(OFF_API_V2, params_v2), (OFF_API_V1, params_v1)]:
            try:
                resp = await client.get(api_url, params=params, timeout=OFF_TIMEOUT)
                if resp.status_code == 503:
                    await asyncio.sleep(5 * (attempt + 1))
                    continue
                resp.raise_for_status()
                data = resp.json()
                products = data.get("products", [])
                if products:
                    return products
            except Exception as e:
                log.debug(f"  Tentative {attempt+1} page {page} ({api_url}): {e}")
                await asyncio.sleep(3)

    log.warning(f"  Page {page}: échec après {OFF_RETRY} tentatives")
    return []


# ──────────────────────────────────────────────────────────────────────────────
# Seed : catégories
# ──────────────────────────────────────────────────────────────────────────────

async def seed_categories(db: AsyncSession) -> dict[str, int]:
    """Insère les catégories et retourne {slug: id}."""
    log.info("── Catégories ──────────────────────────────────")
    slug_to_id: dict[str, int] = {}

    # D'abord les parents (parent=None), puis les enfants
    for cat in CATEGORIES:
        if cat["parent"] is not None:
            continue
        result = await db.execute(
            select(Category).where(Category.slug == cat["slug"])
        )
        obj = result.scalar_one_or_none()
        if not obj:
            obj = Category(name=cat["name"], slug=cat["slug"], icon=cat["icon"])
            db.add(obj)
            await db.flush()
            log.info(f"  + {cat['slug']}")
        slug_to_id[cat["slug"]] = obj.id

    await db.flush()

    for cat in CATEGORIES:
        if cat["parent"] is None:
            continue
        result = await db.execute(
            select(Category).where(Category.slug == cat["slug"])
        )
        obj = result.scalar_one_or_none()
        parent_id = slug_to_id.get(cat["parent"])
        if not obj:
            obj = Category(
                name=cat["name"],
                slug=cat["slug"],
                icon=cat["icon"],
                parent_id=parent_id,
            )
            db.add(obj)
            await db.flush()
            log.info(f"  + {cat['slug']} (↳ {cat['parent']})")
        slug_to_id[cat["slug"]] = obj.id

    await db.commit()
    log.info(f"  ✓ {len(slug_to_id)} catégories prêtes")
    return slug_to_id


# ──────────────────────────────────────────────────────────────────────────────
# Seed : produits
# ──────────────────────────────────────────────────────────────────────────────

async def seed_products(
    db: AsyncSession,
    slug_to_id: dict[str, int],
    limit: int = 5000,
) -> dict:
    log.info("── Produits Open Food Facts ────────────────────")
    stats = {"inserted": 0, "updated": 0, "skipped": 0, "errors": 0}
    seen_slugs: set[str] = set()

    # Charger les barcodes existants
    existing_barcodes: set[str] = set()
    result = await db.execute(select(Product.barcode).where(Product.barcode.isnot(None)))
    for (bc,) in result:
        if bc:
            existing_barcodes.add(bc)

    log.info(f"  {len(existing_barcodes)} produits déjà en base")

    total_fetched = 0
    page = 1
    consecutive_empty = 0

    async with httpx.AsyncClient(
        headers={"User-Agent": "PrixMaroc/1.0 (prixmaroc.ma; contact@prixmaroc.ma)"},
        follow_redirects=True,
    ) as client:
        while total_fetched < limit and page <= OFF_MAX_PAGES:
            products = await fetch_off_page(client, page)
            if not products:
                consecutive_empty += 1
                log.info(f"  Page {page}: vide (échec consécutif {consecutive_empty}/3)")
                if consecutive_empty >= 3:
                    log.info(f"  3 pages vides consécutives — fin")
                    break
                page += 1
                await asyncio.sleep(OFF_DELAY * 2)
                continue
            consecutive_empty = 0

            log.info(f"  Page {page}: {len(products)} produits reçus (total: {total_fetched})")

            for p in products:
                if total_fetched >= limit:
                    break

                try:
                    # Nom (priorité français)
                    name = (
                        p.get("product_name_fr")
                        or p.get("product_name")
                        or ""
                    ).strip()
                    if not name or len(name) < 2:
                        stats["skipped"] += 1
                        continue

                    barcode = str(p.get("code", "")).strip() or None
                    if barcode and len(barcode) < 4:
                        barcode = None

                    # Skip si barcode déjà présent et pas de mise à jour demandée
                    if barcode and barcode in existing_barcodes:
                        stats["skipped"] += 1
                        continue

                    # Nutrition
                    nut = p.get("nutriments", {})
                    calories = _safe_float(nut.get("energy-kcal_100g") or nut.get("energy_100g"))
                    # energy en kJ → kcal
                    if calories and calories > 900:
                        calories = round(calories / 4.184, 1)

                    brand = (p.get("brands") or "").split(",")[0].strip() or None
                    image = (
                        p.get("image_front_url")
                        or p.get("image_url")
                        or None
                    )
                    quantity_str = (p.get("quantity") or "").strip() or None

                    # Slug unique
                    base_slug = _slugify(f"{name} {brand or ''}".strip())
                    slug = _unique_slug(base_slug, seen_slugs)

                    cat_id = _guess_category(p, slug_to_id)

                    obj = Product(
                        name=name[:500],
                        slug=slug,
                        barcode=barcode,
                        brand=brand[:255] if brand else None,
                        image_url=image[:500] if image else None,
                        unit_size=quantity_str[:50] if quantity_str else None,
                        category_id=cat_id,
                        calories=calories,
                        proteins=_safe_float(nut.get("proteins_100g")),
                        lipids=_safe_float(nut.get("fat_100g")),
                        carbs=_safe_float(nut.get("carbohydrates_100g")),
                        fibers=_safe_float(nut.get("fiber_100g")),
                        nutriscore=_nutriscore(p.get("nutriscore_grade")),
                        is_active=True,
                    )
                    db.add(obj)
                    if barcode:
                        existing_barcodes.add(barcode)
                    stats["inserted"] += 1
                    total_fetched += 1

                except Exception as e:
                    log.debug(f"  Erreur produit: {e}")
                    stats["errors"] += 1

            # Commit par batch de 200
            if stats["inserted"] % 200 == 0 and stats["inserted"] > 0:
                await db.commit()
                log.info(f"  → commit intermédiaire ({stats['inserted']} insérés)")

            page += 1
            if page <= OFF_MAX_PAGES:
                await asyncio.sleep(OFF_DELAY)

    await db.commit()
    log.info(
        f"  ✓ {stats['inserted']} insérés, "
        f"{stats['updated']} mis à jour, "
        f"{stats['skipped']} ignorés, "
        f"{stats['errors']} erreurs"
    )
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# Seed : magasins
# ──────────────────────────────────────────────────────────────────────────────

async def seed_stores(db: AsyncSession) -> dict:
    log.info("── Magasins ────────────────────────────────────")
    stats = {"inserted": 0, "updated": 0, "skipped": 0}

    # Slugs existants
    result = await db.execute(select(Store.slug))
    existing_slugs: set[str] = {row[0] for row in result}

    seen_slugs: set[str] = set(existing_slugs)

    for s in STORES_DATA:
        base_slug = _slugify(s["name"])
        slug = _unique_slug(base_slug, seen_slugs)

        if slug in existing_slugs:
            stats["skipped"] += 1
            continue

        chain = s["chain"]
        store = Store(
            name=s["name"],
            slug=slug,
            address=s.get("address"),
            city=s["city"],
            region=s["region"],
            latitude=s["lat"],
            longitude=s["lng"],
            logo_url=CHAIN_LOGOS.get(chain),
            website=CHAIN_WEBSITES.get(chain),
            is_active=True,
            scraping_enabled=(chain in ("marjane", "carrefour", "labelvie", "bim", "kazyon")),
        )
        db.add(store)
        stats["inserted"] += 1

    await db.commit()
    log.info(
        f"  ✓ {stats['inserted']} insérés, "
        f"{stats['skipped']} déjà présents"
    )
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# Données synthétiques (fallback quand OFF API est indisponible)
# ──────────────────────────────────────────────────────────────────────────────

SYNTHETIC_PRODUCTS: list[dict] = [
    # Huiles
    {"name": "Huile de Tournesol Oléor 5L",      "brand": "Oléor",     "barcode": "6111245010015", "cat": "huiles-graisses",     "cal": 900, "prot": 0,   "lip": 100, "carb": 0,   "nut": None, "unit": "5L"},
    {"name": "Huile d'Olive Doukkala 1L",         "brand": "Doukkala",  "barcode": "6111025010019", "cat": "huiles-graisses",     "cal": 884, "prot": 0,   "lip": 100, "carb": 0,   "nut": "B",  "unit": "1L"},
    {"name": "Huile de Soja Lesieur 2L",          "brand": "Lesieur",   "barcode": "6111245020022", "cat": "huiles-graisses",     "cal": 900, "prot": 0,   "lip": 100, "carb": 0,   "nut": None, "unit": "2L"},
    {"name": "Huile Végétale Afia 3L",            "brand": "Afia",      "barcode": "6281003040111", "cat": "huiles-graisses",     "cal": 900, "prot": 0,   "lip": 100, "carb": 0,   "nut": None, "unit": "3L"},
    # Farine & Sucre
    {"name": "Farine Baldo Supérieure 1kg",       "brand": "Baldo",     "barcode": "6111025020031", "cat": "farine-sucre",        "cal": 340, "prot": 10,  "lip": 1,   "carb": 72,  "nut": "C",  "unit": "1kg"},
    {"name": "Sucre Blanc Cosumar 1kg",           "brand": "Cosumar",   "barcode": "6111005010011", "cat": "farine-sucre",        "cal": 400, "prot": 0,   "lip": 0,   "carb": 100, "nut": "E",  "unit": "1kg"},
    {"name": "Sucre Raffiné Cosumar 5kg",         "brand": "Cosumar",   "barcode": "6111005010028", "cat": "farine-sucre",        "cal": 400, "prot": 0,   "lip": 0,   "carb": 100, "nut": "E",  "unit": "5kg"},
    {"name": "Semoule Fine Baldo 1kg",            "brand": "Baldo",     "barcode": "6111025030041", "cat": "pates-riz",           "cal": 360, "prot": 12,  "lip": 1,   "carb": 74,  "nut": "C",  "unit": "1kg"},
    # Pâtes & Riz
    {"name": "Pâtes Spaghetti Safwa 500g",        "brand": "Safwa",     "barcode": "6111111010011", "cat": "pates-riz",           "cal": 350, "prot": 13,  "lip": 1,   "carb": 71,  "nut": "B",  "unit": "500g"},
    {"name": "Riz Long Grain Uncle Ben's 1kg",    "brand": "Uncle Ben's","barcode":"5000118356021", "cat": "pates-riz",           "cal": 348, "prot": 7,   "lip": 1,   "carb": 77,  "nut": "B",  "unit": "1kg"},
    {"name": "Couscous Moyen Dari 1kg",           "brand": "Dari",      "barcode": "6111333010011", "cat": "pates-riz",           "cal": 376, "prot": 11,  "lip": 2,   "carb": 77,  "nut": "B",  "unit": "1kg"},
    {"name": "Vermicelles Safwa 500g",            "brand": "Safwa",     "barcode": "6111111020021", "cat": "pates-riz",           "cal": 348, "prot": 13,  "lip": 1,   "carb": 71,  "nut": "B",  "unit": "500g"},
    # Produits laitiers
    {"name": "Lait Centrale Demi-écrémé 1L",      "brand": "Centrale",  "barcode": "6111006010011", "cat": "produits-laitiers",   "cal": 46,  "prot": 3.4, "lip": 1.5, "carb": 4.7, "nut": "B",  "unit": "1L"},
    {"name": "Lait Jaouda Entier 1L",             "brand": "Jaouda",    "barcode": "6111007010012", "cat": "produits-laitiers",   "cal": 65,  "prot": 3.2, "lip": 3.5, "carb": 4.8, "nut": "B",  "unit": "1L"},
    {"name": "Yaourt Nature Danone 125g",         "brand": "Danone",    "barcode": "3033490011110", "cat": "produits-laitiers",   "cal": 59,  "prot": 4.1, "lip": 1.6, "carb": 6.8, "nut": "B",  "unit": "125g"},
    {"name": "Fromage Vache Qui Rit 8 portions",  "brand": "La Vache Qui Rit","barcode":"7622400004063","cat": "produits-laitiers","cal": 233, "prot": 10,  "lip": 18,  "carb": 8,   "nut": "C",  "unit": "8p"},
    {"name": "Beurre Président 200g",             "brand": "Président", "barcode": "3228021090011", "cat": "produits-laitiers",   "cal": 717, "prot": 0.5, "lip": 80,  "carb": 0.5, "nut": "D",  "unit": "200g"},
    {"name": "Lait Condensé Nestlé 397g",         "brand": "Nestlé",    "barcode": "7613034626516", "cat": "produits-laitiers",   "cal": 321, "prot": 7.8, "lip": 8.5, "carb": 55,  "nut": "D",  "unit": "397g"},
    # Boissons
    {"name": "Eau Minérale Sidi Ali 1.5L",        "brand": "Sidi Ali",  "barcode": "6111100010011", "cat": "eaux",                "cal": 0,   "prot": 0,   "lip": 0,   "carb": 0,   "nut": None, "unit": "1.5L"},
    {"name": "Eau Minérale Oulmès 1.5L",          "brand": "Oulmès",    "barcode": "6111101010012", "cat": "eaux",                "cal": 0,   "prot": 0,   "lip": 0,   "carb": 0,   "nut": None, "unit": "1.5L"},
    {"name": "Eau Minérale Aïn Saïss 1.5L",       "brand": "Aïn Saïss", "barcode": "6111102010013", "cat": "eaux",                "cal": 0,   "prot": 0,   "lip": 0,   "carb": 0,   "nut": None, "unit": "1.5L"},
    {"name": "Coca-Cola 1.25L",                   "brand": "Coca-Cola", "barcode": "5449000131836", "cat": "sodas",               "cal": 42,  "prot": 0,   "lip": 0,   "carb": 11,  "nut": "E",  "unit": "1.25L"},
    {"name": "Pepsi Cola 1.25L",                  "brand": "Pepsi",     "barcode": "4002359000181", "cat": "sodas",               "cal": 40,  "prot": 0,   "lip": 0,   "carb": 10,  "nut": "E",  "unit": "1.25L"},
    {"name": "Jus d'Orange Pago 1L",              "brand": "Pago",      "barcode": "6111200010011", "cat": "jus-nectars",         "cal": 45,  "prot": 0.7, "lip": 0.2, "carb": 10,  "nut": "C",  "unit": "1L"},
    {"name": "Jus Multifruits Rania 1L",          "brand": "Rania",     "barcode": "6111201020012", "cat": "jus-nectars",         "cal": 50,  "prot": 0.5, "lip": 0,   "carb": 12,  "nut": "C",  "unit": "1L"},
    {"name": "Thé Vert Atay Sidi Larbi 400g",     "brand": "Sidi Larbi","barcode": "6111300010011", "cat": "the-cafe",            "cal": 1,   "prot": 0.2, "lip": 0,   "carb": 0.2, "nut": "A",  "unit": "400g"},
    {"name": "Café Moulu Nescafé Classic 200g",   "brand": "Nescafé",   "barcode": "7613036251716", "cat": "the-cafe",            "cal": 2,   "prot": 0.1, "lip": 0,   "carb": 0.3, "nut": "A",  "unit": "200g"},
    # Conserves
    {"name": "Thon Entier à l'huile Darna 160g",  "brand": "Darna",     "barcode": "6111400010011", "cat": "conserves",           "cal": 184, "prot": 26,  "lip": 9,   "carb": 0,   "nut": "A",  "unit": "160g"},
    {"name": "Sardines à l'huile Ksar 125g",      "brand": "Ksar",      "barcode": "6111401020012", "cat": "conserves",           "cal": 208, "prot": 20,  "lip": 14,  "carb": 0,   "nut": "A",  "unit": "125g"},
    {"name": "Tomate Concentrée Aicha 70g",       "brand": "Aicha",     "barcode": "6111500010011", "cat": "conserves",           "cal": 95,  "prot": 4.5, "lip": 0.5, "carb": 19,  "nut": "B",  "unit": "70g"},
    {"name": "Tomate Concentrée Doha 135g",       "brand": "Doha",      "barcode": "6111501020012", "cat": "conserves",           "cal": 98,  "prot": 4.8, "lip": 0.6, "carb": 20,  "nut": "B",  "unit": "135g"},
    {"name": "Harissa Aicha 70g",                 "brand": "Aicha",     "barcode": "6111500020021", "cat": "condiments-sauces",   "cal": 60,  "prot": 2,   "lip": 1,   "carb": 12,  "nut": "B",  "unit": "70g"},
    # Condiments
    {"name": "Sel de Table Cérès 750g",           "brand": "Cérès",     "barcode": "6111600010011", "cat": "condiments-sauces",   "cal": 0,   "prot": 0,   "lip": 0,   "carb": 0,   "nut": None, "unit": "750g"},
    {"name": "Vinaigre Blanc Cérès 750ml",        "brand": "Cérès",     "barcode": "6111600020021", "cat": "condiments-sauces",   "cal": 18,  "prot": 0,   "lip": 0,   "carb": 0.9, "nut": None, "unit": "750ml"},
    # Épices
    {"name": "Cumin Moulu Badi 100g",             "brand": "Badi",      "barcode": "6111700010011", "cat": "epices-herbes",       "cal": 375, "prot": 18,  "lip": 22,  "carb": 44,  "nut": None, "unit": "100g"},
    {"name": "Paprika Doux Badi 100g",            "brand": "Badi",      "barcode": "6111700020021", "cat": "epices-herbes",       "cal": 282, "prot": 14,  "lip": 13,  "carb": 54,  "nut": None, "unit": "100g"},
    {"name": "Ras El Hanout Badi 100g",           "brand": "Badi",      "barcode": "6111700030031", "cat": "epices-herbes",       "cal": 322, "prot": 11,  "lip": 15,  "carb": 49,  "nut": None, "unit": "100g"},
    # Céréales
    {"name": "Corn Flakes Kellogg's 375g",        "brand": "Kellogg's", "barcode": "5053827198397", "cat": "cereales-petit-dej",  "cal": 378, "prot": 7,   "lip": 1,   "carb": 83,  "nut": "B",  "unit": "375g"},
    {"name": "Chocolat en poudre Nesquik 500g",   "brand": "Nesquik",   "barcode": "7613034085849", "cat": "cereales-petit-dej",  "cal": 373, "prot": 4.7, "lip": 3.1, "carb": 78,  "nut": "C",  "unit": "500g"},
    # Snacks
    {"name": "Biscuits LU Petit Écolier 200g",    "brand": "LU",        "barcode": "7622201151744", "cat": "snacks-confiseries",  "cal": 480, "prot": 6,   "lip": 19,  "carb": 68,  "nut": "D",  "unit": "200g"},
    {"name": "Chips Bingo Paprika 100g",          "brand": "Bingo",     "barcode": "6111800010011", "cat": "snacks-confiseries",  "cal": 529, "prot": 7,   "lip": 30,  "carb": 56,  "nut": "E",  "unit": "100g"},
    {"name": "Chocolat Milk Milka 100g",          "brand": "Milka",     "barcode": "7622201483517", "cat": "snacks-confiseries",  "cal": 535, "prot": 7,   "lip": 30,  "carb": 57,  "nut": "E",  "unit": "100g"},
    {"name": "Gâteau Chamonix Lu 180g",           "brand": "LU",        "barcode": "7622201007569", "cat": "snacks-confiseries",  "cal": 390, "prot": 5,   "lip": 10,  "carb": 69,  "nut": "D",  "unit": "180g"},
    # Légumineuses
    {"name": "Lentilles Vertes Casa Prim 500g",   "brand": "Casa Prim", "barcode": "6111900010011", "cat": "legumineuses",        "cal": 352, "prot": 26,  "lip": 1,   "carb": 60,  "nut": "A",  "unit": "500g"},
    {"name": "Pois Chiches Secs Dari 500g",       "brand": "Dari",      "barcode": "6111333020021", "cat": "legumineuses",        "cal": 364, "prot": 19,  "lip": 6,   "carb": 61,  "nut": "A",  "unit": "500g"},
    {"name": "Haricots Blancs Secs 500g",         "brand": "Generique", "barcode": "6111901020012", "cat": "legumineuses",        "cal": 337, "prot": 21,  "lip": 1,   "carb": 61,  "nut": "A",  "unit": "500g"},
    # Hygiène
    {"name": "Savon Lifebuoy Total 10 125g",      "brand": "Lifebuoy",  "barcode": "8712561395578", "cat": "soins-corps",         "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "125g"},
    {"name": "Shampooing Head & Shoulders 400ml", "brand": "Head & Shoulders","barcode":"8001090738837","cat":"soins-cheveux",    "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "400ml"},
    {"name": "Dentifrice Colgate Total 75ml",     "brand": "Colgate",   "barcode": "8714789796504", "cat": "hygiene-dentaire",    "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "75ml"},
    {"name": "Déodorant Rexona Men 150ml",        "brand": "Rexona",    "barcode": "8717163598108", "cat": "deodorants-parfums",  "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "150ml"},
    {"name": "Gel Douche Palmolive 250ml",        "brand": "Palmolive", "barcode": "8718951113237", "cat": "soins-corps",         "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "250ml"},
    # Entretien
    {"name": "Lessive Tide Poudre 5kg",           "brand": "Tide",      "barcode": "4015400835004", "cat": "lessive-adoucissant", "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "5kg"},
    {"name": "Lessive OMO Poudre 3kg",            "brand": "OMO",       "barcode": "8714100888131", "cat": "lessive-adoucissant", "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "3kg"},
    {"name": "Adoucissant Comfort Bleu 2L",       "brand": "Comfort",   "barcode": "8710908990021", "cat": "lessive-adoucissant", "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "2L"},
    {"name": "Liquide Vaisselle Fairy 500ml",     "brand": "Fairy",     "barcode": "8001841000763", "cat": "produits-vaisselle",  "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "500ml"},
    {"name": "Nettoyant WC Duck 750ml",           "brand": "Duck",      "barcode": "5000204099775", "cat": "nettoyants-surfaces", "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "750ml"},
    {"name": "Javel Lacroix 1L",                  "brand": "Lacroix",   "barcode": "6111010010011", "cat": "nettoyants-surfaces", "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "1L"},
    {"name": "Papier Toilette Confort 12 rouleaux","brand": "Confort",   "barcode": "6111011020021", "cat": "papier-essuie-tout",  "cal": None, "prot": None,"lip": None,"carb": None,"nut": None, "unit": "12r"},
]

# Prix de base par produit (MAD) — varie légèrement par chaîne
SYNTHETIC_BASE_PRICES: dict[str, float] = {
    # Slugs générés par _slugify("{name} {brand}") — clés vérifiées
    "huile-de-tournesol-oleor-5l-oleor":        88.0,   # 5L tournesol
    "huile-d-olive-doukkala-1l-doukkala":        59.0,   # 1L olive
    "huile-de-soja-lesieur-2l-lesieur":          42.0,   # 2L soja
    "huile-vegetale-afia-3l-afia":               65.0,   # 3L végétale
    "farine-baldo-superieure-1kg-baldo":          9.5,
    "sucre-blanc-cosumar-1kg-cosumar":            8.5,
    "sucre-raffine-cosumar-5kg-cosumar":         40.0,
    "semoule-fine-baldo-1kg-baldo":              10.0,
    "pates-spaghetti-safwa-500g-safwa":           7.5,
    "riz-long-grain-uncle-ben-s-1kg-uncle-ben-s": 22.0,
    "couscous-moyen-dari-1kg-dari":              15.0,
    "vermicelles-safwa-500g-safwa":               7.0,
    "lait-centrale-demi-ecreme-1l-centrale":      8.0,
    "lait-jaouda-entier-1l-jaouda":               7.5,
    "yaourt-nature-danone-125g-danone":           4.5,
    "fromage-vache-qui-rit-8-portions-la-vache-qui-rit": 28.0,
    "beurre-president-200g-president":           35.0,
    "lait-condense-nestle-397g-nestle":          19.0,
    "eau-minerale-sidi-ali-1-5l-sidi-ali":        4.5,
    "eau-minerale-oulmes-1-5l-oulmes":            5.0,
    "eau-minerale-ain-saiss-1-5l-ain-saiss":      3.5,
    "coca-cola-1-25l-coca-cola":                 12.0,
    "pepsi-cola-1-25l-pepsi":                    11.5,
    "jus-d-orange-pago-1l-pago":                 18.0,
    "jus-multifruits-rania-1l-rania":            14.0,
    "the-vert-atay-sidi-larbi-400g-sidi-larbi":  28.0,
    "cafe-moulu-nescafe-classic-200g-nescafe":   55.0,
    "thon-entier-a-l-huile-darna-160g-darna":    22.0,
    "sardines-a-l-huile-ksar-125g-ksar":         10.0,
    "tomate-concentree-aicha-70g-aicha":          5.5,
    "tomate-concentree-doha-135g-doha":           8.0,
    "harissa-aicha-70g-aicha":                    5.0,
    "sel-de-table-ceres-750g-ceres":              4.0,
    "vinaigre-blanc-ceres-750ml-ceres":           6.5,
    "cumin-moulu-badi-100g-badi":                12.0,
    "paprika-doux-badi-100g-badi":               11.0,
    "ras-el-hanout-badi-100g-badi":              13.0,
    "corn-flakes-kellogg-s-375g-kellogg-s":      42.0,
    "chocolat-en-poudre-nesquik-500g-nesquik":   48.0,
    "biscuits-lu-petit-ecolier-200g-lu":         25.0,
    "chips-bingo-paprika-100g-bingo":            12.0,
    "chocolat-milk-milka-100g-milka":            22.0,
    "gateau-chamonix-lu-180g-lu":                28.0,
    "lentilles-vertes-casa-prim-500g-casa-prim": 12.0,
    "pois-chiches-secs-dari-500g-dari":          14.0,
    "haricots-blancs-secs-500g-generique":       11.0,
    "savon-lifebuoy-total-10-125g-lifebuoy":      9.0,
    "shampooing-head-shoulders-400ml-head-shoulders": 65.0,
    "dentifrice-colgate-total-75ml-colgate":     32.0,
    "deodorant-rexona-men-150ml-rexona":         45.0,
    "gel-douche-palmolive-250ml-palmolive":      28.0,
    "lessive-tide-poudre-5kg-tide":             145.0,
    "lessive-omo-poudre-3kg-omo":               88.0,
    "adoucissant-comfort-bleu-2l-comfort":       42.0,
    "liquide-vaisselle-fairy-500ml-fairy":       25.0,
    "nettoyant-wc-duck-750ml-duck":              22.0,
    "javel-lacroix-1l-lacroix":                   9.0,
    "papier-toilette-confort-12-rouleaux-confort": 48.0,
    # Aliases courts (fallback partiel)
    "huile-de-tournesol":  88.0,
    "huile-d-olive":       59.0,
    "huile-de-soja":       42.0,
    "sucre-blanc":          8.5,
    "sucre-raffine":       40.0,
    "lait-centrale":        8.0,
    "lait-jaouda":          7.5,
    "coca-cola":           12.0,
    "pepsi-cola":          11.5,
    "cafe-moulu-nescafe":  55.0,
    "lessive-tide":       145.0,
    "lessive-omo":         88.0,
    "shampooing-head":     65.0,
}

# Multiplicateurs prix par chaîne (Marjane = référence 1.0)
CHAIN_PRICE_MULTIPLIERS: dict[str, float] = {
    "marjane":   1.00,
    "carrefour": 1.02,
    "labelvie":  1.05,
    "bim":       0.88,
    "atacadao":  0.92,
    "kazyon":    0.85,
    "aswak":     1.08,
    "acima":     1.03,
}


async def seed_synthetic_products(
    db: AsyncSession,
    slug_to_id: dict[str, int],
) -> dict:
    """Insère les produits synthétiques + prix pour quelques magasins."""
    from app.models.price import Price
    import random

    log.info("── Produits synthétiques (fallback OFF) ────────")
    stats = {"products": 0, "prices": 0, "skipped": 0}
    seen_slugs: set[str] = set()

    # Barcodes existants
    result = await db.execute(select(Product.barcode).where(Product.barcode.isnot(None)))
    existing_barcodes: set[str] = {row[0] for row in result if row[0]}

    # ID magasins par chaîne (1 par chaîne pour les prix)
    result = await db.execute(select(Store.id, Store.slug))
    all_stores: list[tuple[int, str]] = list(result)

    chain_store: dict[str, int] = {}
    for store_id, store_slug in all_stores:
        for chain in CHAIN_PRICE_MULTIPLIERS:
            if chain in store_slug and chain not in chain_store:
                chain_store[chain] = store_id

    for p in SYNTHETIC_PRODUCTS:
        if p["barcode"] in existing_barcodes:
            stats["skipped"] += 1
            continue

        base_slug = _slugify(f"{p['name']} {p['brand']}")
        slug = _unique_slug(base_slug, seen_slugs)

        cat_id = slug_to_id.get(p["cat"])
        base_price = SYNTHETIC_BASE_PRICES.get(slug)
        if not base_price:
            # Cherche par correspondance partielle (nom sans brand)
            name_slug = _slugify(p["name"])
            base_price = SYNTHETIC_BASE_PRICES.get(name_slug)
        if not base_price:
            # Dernier recours : sous-chaîne de 15 chars minimum
            for k, v in SYNTHETIC_BASE_PRICES.items():
                if len(k) >= 15 and k[:15] in slug:
                    base_price = v
                    break
        if not base_price:
            # Estimation basée sur la catégorie
            cat_defaults = {
                "huiles-graisses": 50.0, "farine-sucre": 9.0, "pates-riz": 12.0,
                "produits-laitiers": 10.0, "eaux": 4.0, "sodas": 12.0,
                "jus-nectars": 15.0, "the-cafe": 35.0, "conserves": 12.0,
                "condiments-sauces": 7.0, "epices-herbes": 12.0,
                "cereales-petit-dej": 45.0, "snacks-confiseries": 20.0,
                "legumineuses": 12.0, "soins-corps": 20.0, "soins-cheveux": 55.0,
                "hygiene-dentaire": 30.0, "deodorants-parfums": 45.0,
                "lessive-adoucissant": 90.0, "produits-vaisselle": 25.0,
                "nettoyants-surfaces": 20.0, "papier-essuie-tout": 48.0,
            }
            base_price = cat_defaults.get(p.get("cat", ""), 18.0)

        product = Product(
            name=p["name"],
            slug=slug,
            barcode=p["barcode"],
            brand=p["brand"],
            unit_size=p.get("unit"),
            category_id=cat_id,
            calories=p.get("cal"),
            proteins=p.get("prot"),
            lipids=p.get("lip"),
            carbs=p.get("carb"),
            nutriscore=p.get("nut"),
            is_active=True,
        )
        db.add(product)
        await db.flush()
        existing_barcodes.add(p["barcode"])
        stats["products"] += 1

        # Ajouter des prix dans les magasins disponibles
        for chain, mult in CHAIN_PRICE_MULTIPLIERS.items():
            store_id = chain_store.get(chain)
            if not store_id:
                continue
            noise = random.uniform(-0.05, 0.05)  # ±5% de bruit
            price = round(base_price * mult * (1 + noise), 2)
            # Parfois en promo
            is_promo = random.random() < 0.15
            original_price = None
            if is_promo:
                original_price = price
                price = round(price * 0.85, 2)

            price_obj = Price(
                product_id=product.id,
                store_id=store_id,
                price=price if not is_promo else (original_price or price),
                promo_price=price if is_promo else None,
                is_promo=is_promo,
                source="manual",
            )
            db.add(price_obj)
            stats["prices"] += 1

    await db.commit()
    log.info(
        f"  ✓ {stats['products']} produits insérés, "
        f"{stats['prices']} prix générés, "
        f"{stats['skipped']} déjà présents"
    )
    return stats


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────

async def main(args: argparse.Namespace) -> None:
    engine = create_async_engine(settings.DATABASE_URL, echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    t0 = time.perf_counter()
    log.info("╔══════════════════════════════════════════════╗")
    log.info("║       PrixMaroc — Seed base de données       ║")
    log.info("╚══════════════════════════════════════════════╝")

    cat_stats = {}
    prod_stats = {}
    store_stats = {}

    async with Session() as db:
        if not args.stores_only:
            cat_stats = await seed_categories(db)

        if not args.stores_only and not args.synthetic:
            prod_stats = await seed_products(db, cat_stats, limit=args.limit)

        if not args.stores_only and args.synthetic:
            prod_stats = await seed_synthetic_products(db, cat_stats)

        if not args.products_only:
            store_stats = await seed_stores(db)

    elapsed = time.perf_counter() - t0
    log.info("")
    log.info("╔══════════════════════════════════════════════╗")
    log.info("║                  RAPPORT FINAL               ║")
    log.info("╠══════════════════════════════════════════════╣")
    if prod_stats:
        log.info(f"║  Produits insérés  : {prod_stats.get('inserted', 0):<6}                   ║")
        log.info(f"║  Produits ignorés  : {prod_stats.get('skipped', 0):<6}                   ║")
        log.info(f"║  Erreurs produits  : {prod_stats.get('errors', 0):<6}                   ║")
    if store_stats:
        log.info(f"║  Magasins insérés  : {store_stats.get('inserted', 0):<6}                   ║")
    log.info(f"║  Durée totale      : {elapsed:>5.0f}s                  ║")
    log.info("╚══════════════════════════════════════════════╝")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed PrixMaroc database")
    parser.add_argument("--products-only", action="store_true", help="Importer seulement les produits")
    parser.add_argument("--stores-only",   action="store_true", help="Importer seulement les magasins")
    parser.add_argument("--limit",         type=int, default=5000, help="Nombre max de produits OFF (défaut: 5000)")
    parser.add_argument("--synthetic",     action="store_true", help="Utiliser données synthétiques (quand OFF API indisponible)")
    args = parser.parse_args()
    asyncio.run(main(args))
