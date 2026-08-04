"""
Seed réaliste avec de vraies données produits marocains.
Prix basés sur les marchés réels (Marjane, Carrefour, BIM, Label'Vie, Atacadão).

Source: Prix de marché marocain connus (DH)
"""
import asyncio
import asyncpg
import re
from datetime import datetime, timedelta, timezone
import random

DATABASE_URL = "postgresql://prixmaroc:prixmaroc@db:5432/prixmaroc"

# ── Produits avec vrais prix marocains ──────────────────────────────────────
# Format: (nom, marque, categorie_slug, image_url, unite, prix_ref_MAD, notes)
# Les prix sont les prix de référence (prix typiques du marché)

PRODUCTS = [
    # ── HUILES & GRAISSES ──────────────────────────────────────────────────
    ("Huile de Tournesol Lesieur 1L", "Lesieur", "epicerie", "lesieur-huile-tournesol-1l", "1L", 24.90, "huile_tournesol_1l"),
    ("Huile de Tournesol Lesieur 2L", "Lesieur", "epicerie", "lesieur-huile-tournesol-2l", "2L", 46.50, "huile_tournesol_2l"),
    ("Huile d'Olive Moulins de la Médina 500ml", "Moulins de la Médina", "epicerie", "moulins-medina-olive-500ml", "500ml", 52.00, "huile_olive_500ml"),
    ("Huile de Soja Cristal 1L", "Cristal", "epicerie", "cristal-soja-1l", "1L", 22.50, "huile_soja_1l"),

    # ── SUCRE & FARINE ──────────────────────────────────────────────────────
    ("Sucre Cosumar 1kg", "Cosumar", "epicerie", "cosumar-sucre-1kg", "1kg", 7.80, "sucre_1kg"),
    ("Sucre Cosumar Pains 1kg", "Cosumar", "epicerie", "cosumar-sucre-pains-1kg", "1kg", 8.50, "sucre_pains_1kg"),
    ("Farine Tendre Ilycia 1kg", "Ilycia", "epicerie", "ilycia-farine-1kg", "1kg", 8.20, "farine_1kg"),
    ("Farine Complète Ilycia 1kg", "Ilycia", "epicerie", "ilycia-farine-complete-1kg", "1kg", 9.50, "farine_complete_1kg"),
    ("Farine Ilycia 5kg", "Ilycia", "epicerie", "ilycia-farine-5kg", "5kg", 38.00, "farine_5kg"),

    # ── PÂTES & RIZ ─────────────────────────────────────────────────────────
    ("Spaghetti Safra 500g", "Safra", "epicerie", "safra-spaghetti-500g", "500g", 6.50, "spaghetti_500g"),
    ("Pâtes Penne Safra 500g", "Safra", "epicerie", "safra-penne-500g", "500g", 6.50, "penne_500g"),
    ("Couscous Dari 1kg", "Dari", "epicerie", "dari-couscous-1kg", "1kg", 11.50, "couscous_1kg"),
    ("Riz Long Grain Américain 1kg", "Taureau Ailé", "epicerie", "taureau-aile-riz-1kg", "1kg", 16.90, "riz_long_1kg"),
    ("Riz Basmati Noor 1kg", "Noor", "epicerie", "noor-riz-basmati-1kg", "1kg", 22.50, "riz_basmati_1kg"),

    # ── CONSERVES ───────────────────────────────────────────────────────────
    ("Tomates Pelées Aïcha 400g", "Aïcha", "epicerie", "aicha-tomates-pelees-400g", "400g", 7.20, "tomates_pelees_400g"),
    ("Double Concentré Tomate Aïcha 130g", "Aïcha", "epicerie", "aicha-concentre-tomate-130g", "130g", 6.80, "concentre_tomate_130g"),
    ("Harissa Aïcha Forte 135g", "Aïcha", "epicerie", "aicha-harissa-forte-135g", "135g", 6.50, "harissa_135g"),
    ("Sardines Aïcha à l'Huile 125g", "Aïcha", "epicerie", "aicha-sardines-huile-125g", "125g", 9.90, "sardines_125g"),
    ("Sardines Saupiquet 135g", "Saupiquet", "epicerie", "saupiquet-sardines-135g", "135g", 12.50, "sardines_saupiquet_135g"),
    ("Thon en Boîte Saupiquet 160g", "Saupiquet", "epicerie", "saupiquet-thon-160g", "160g", 19.90, "thon_160g"),

    # ── CAFÉ & THÉ ──────────────────────────────────────────────────────────
    ("Café Soluble Nescafé Classic 200g", "Nescafé", "epicerie", "nescafe-classic-200g", "200g", 52.00, "nescafe_200g"),
    ("Café Amara 250g", "Amara", "epicerie", "amara-cafe-250g", "250g", 38.50, "cafe_amara_250g"),
    ("Thé Lipton Yellow Label 25 sachets", "Lipton", "epicerie", "lipton-yellow-25", "25 sachets", 19.90, "lipton_25"),
    ("Thé Atay Touareg 100g", "Atay", "epicerie", "atay-touareg-100g", "100g", 24.50, "atay_100g"),

    # ── PRODUITS LAITIERS ───────────────────────────────────────────────────
    ("Lait UHT Entier Jaouda 1L", "Jaouda", "produits-frais", "jaouda-lait-entier-1l", "1L", 7.90, "lait_entier_1l"),
    ("Lait UHT Demi-écrémé Centrale 1L", "Centrale", "produits-frais", "centrale-lait-demi-1l", "1L", 7.50, "lait_demi_1l"),
    ("Yaourt Nature Danone 125g x4", "Danone", "produits-frais", "danone-yaourt-nature-4x125g", "4x125g", 14.90, "yaourt_nature_4x125"),
    ("Yaourt Activia Danone 125g x4", "Danone", "produits-frais", "danone-activia-4x125g", "4x125g", 16.50, "activia_4x125"),
    ("Beurre Président 250g", "Président", "produits-frais", "president-beurre-250g", "250g", 31.50, "beurre_250g"),
    ("Fromage Fondu La Vache Qui Rit 280g", "La Vache Qui Rit", "produits-frais", "vqr-280g", "280g", 27.90, "vqr_280g"),
    ("Fromage Fondu Kiri 12 portions", "Kiri", "produits-frais", "kiri-12-portions", "12 portions", 24.90, "kiri_12"),

    # ── BOISSONS ────────────────────────────────────────────────────────────
    ("Eau Minérale Sidi Ali 1.5L", "Sidi Ali", "boissons", "sidi-ali-1-5l", "1.5L", 5.50, "sidi_ali_1_5l"),
    ("Eau Minérale Sidi Ali 5L", "Sidi Ali", "boissons", "sidi-ali-5l", "5L", 14.90, "sidi_ali_5l"),
    ("Eau Minérale Bahia 1.5L", "Bahia", "boissons", "bahia-1-5l", "1.5L", 4.90, "bahia_1_5l"),
    ("Coca-Cola 1.5L", "Coca-Cola", "boissons", "coca-cola-1-5l", "1.5L", 14.50, "coca_cola_1_5l"),
    ("Coca-Cola 330ml Canette", "Coca-Cola", "boissons", "coca-cola-canette-330ml", "330ml", 7.50, "coca_cola_330ml"),
    ("Pepsi 1.5L", "Pepsi", "boissons", "pepsi-1-5l", "1.5L", 13.90, "pepsi_1_5l"),
    ("Jus d'Orange Rajo 1L", "Rajo", "boissons", "rajo-jus-orange-1l", "1L", 15.90, "rajo_orange_1l"),
    ("Jus de Raisin Raibi Jaouda 1L", "Jaouda", "boissons", "jaouda-raibi-1l", "1L", 13.50, "raibi_1l"),
    ("Lipton Ice Tea Pêche 1.5L", "Lipton", "boissons", "lipton-ice-tea-peche-1-5l", "1.5L", 16.90, "lipton_peche_1_5l"),

    # ── HYGIÈNE & BEAUTÉ ────────────────────────────────────────────────────
    ("Shampooing Pantene Pro-V 400ml", "Pantene", "hygiene-beaute", "pantene-prov-400ml", "400ml", 39.90, "pantene_400ml"),
    ("Shampooing Head & Shoulders 400ml", "Head & Shoulders", "hygiene-beaute", "h-s-400ml", "400ml", 42.50, "hs_400ml"),
    ("Savon Dove Beauty Bar 90g", "Dove", "hygiene-beaute", "dove-bar-90g", "90g", 14.50, "dove_90g"),
    ("Gel Douche Fa 250ml", "Fa", "hygiene-beaute", "fa-gel-250ml", "250ml", 22.90, "fa_250ml"),
    ("Dentifrice Colgate Triple Action 75ml", "Colgate", "hygiene-beaute", "colgate-triple-75ml", "75ml", 19.90, "colgate_75ml"),
    ("Déodorant Nivea Roll-On 50ml", "Nivea", "hygiene-beaute", "nivea-roll-50ml", "50ml", 28.50, "nivea_50ml"),

    # ── ENTRETIEN MAISON ────────────────────────────────────────────────────
    ("Lessive Tide 1kg", "Tide", "entretien", "tide-1kg", "1kg", 44.90, "tide_1kg"),
    ("Lessive OMO 1kg", "OMO", "entretien", "omo-1kg", "1kg", 42.50, "omo_1kg"),
    ("Eau de Javel Ajax 1L", "Ajax", "entretien", "ajax-javel-1l", "1L", 8.90, "ajax_1l"),
    ("Liquide Vaisselle Paic 500ml", "Paic", "entretien", "paic-500ml", "500ml", 12.50, "paic_500ml"),
    ("Nettoyant WC Canard 750ml", "Canard", "entretien", "canard-750ml", "750ml", 24.90, "canard_750ml"),
    ("Papier Toilette Lotus 8 rouleaux", "Lotus", "entretien", "lotus-8r", "8 rouleaux", 34.90, "lotus_8r"),

    # ── PRODUITS LAITIERS FRAIS ─────────────────────────────────────────────
    ("Fromage Raibi Jaouda 500g", "Jaouda", "produits-frais", "jaouda-raibi-500g", "500g", 19.90, "raibi_500g"),
    ("Crème Fraîche Président 20cl", "Président", "produits-frais", "president-creme-20cl", "20cl", 16.90, "creme_20cl"),
    ("Margarine Fleurial 250g", "Fleurial", "produits-frais", "fleurial-250g", "250g", 14.90, "fleurial_250g"),
    ("Fromage Blanc Danone 500g", "Danone", "produits-frais", "danone-fromage-blanc-500g", "500g", 18.50, "fromage_blanc_500g"),

    # ── LÉGUMES FRAIS ────────────────────────────────────────────────────────
    # Prix de marché marocain (souk + grande surface) — réf. Marjane/Carrefour 2024
    ("Tomates Fraîches 1kg", "Vrac", "produits-frais", "tomates-fraiches-1kg", "1kg", 5.50, "tomates_fraiches_1kg"),
    ("Oignons 1kg", "Vrac", "produits-frais", "oignons-1kg", "1kg", 3.00, "oignons_1kg"),
    ("Pommes de Terre 1kg", "Vrac", "produits-frais", "pommes-de-terre-1kg", "1kg", 5.00, "pommes_terre_1kg"),
    ("Carottes 1kg", "Vrac", "produits-frais", "carottes-1kg", "1kg", 4.00, "carottes_1kg"),
    ("Courgettes 1kg", "Vrac", "produits-frais", "courgettes-1kg", "1kg", 6.50, "courgettes_1kg"),
    ("Poivrons 1kg", "Vrac", "produits-frais", "poivrons-1kg", "1kg", 9.00, "poivrons_1kg"),
    ("Aubergines 1kg", "Vrac", "produits-frais", "aubergines-1kg", "1kg", 7.00, "aubergines_1kg"),
    ("Navets 1kg", "Vrac", "produits-frais", "navets-1kg", "1kg", 4.00, "navets_1kg"),
    ("Petits Pois Surgelés 1kg", "Bonduelle", "produits-frais", "bonduelle-petits-pois-1kg", "1kg", 18.90, "petits_pois_surgeles_1kg"),
    ("Chou Blanc 1kg", "Vrac", "produits-frais", "chou-blanc-1kg", "1kg", 3.50, "chou_blanc_1kg"),
    ("Ail 250g", "Vrac", "produits-frais", "ail-250g", "250g", 8.00, "ail_250g"),
    ("Persil Coriandre Bouquet", "Vrac", "produits-frais", "persil-coriandre-bouquet", "bouquet", 2.00, "persil_bouquet"),
    ("Epinards Frais 500g", "Vrac", "produits-frais", "epinards-frais-500g", "500g", 5.00, "epinards_500g"),
    ("Haricots Verts 500g", "Vrac", "produits-frais", "haricots-verts-500g", "500g", 7.00, "haricots_verts_500g"),
    ("Betteraves 1kg", "Vrac", "produits-frais", "betteraves-1kg", "1kg", 4.50, "betteraves_1kg"),

    # ── FRUITS FRAIS ─────────────────────────────────────────────────────────
    # Fruits de saison marocains (agrumes, fruits estivaux, fruits secs)
    ("Oranges 1kg", "Vrac", "produits-frais", "oranges-1kg", "1kg", 5.00, "oranges_1kg"),
    ("Pommes 1kg", "Vrac", "produits-frais", "pommes-1kg", "1kg", 12.00, "pommes_1kg"),
    ("Bananes 1kg", "Vrac", "produits-frais", "bananes-1kg", "1kg", 10.00, "bananes_1kg"),
    ("Clémentines 1kg", "Vrac", "produits-frais", "clementines-1kg", "1kg", 8.00, "clementines_1kg"),
    ("Grenades 1kg", "Vrac", "produits-frais", "grenades-1kg", "1kg", 12.00, "grenades_1kg"),
    ("Raisins 1kg", "Vrac", "produits-frais", "raisins-1kg", "1kg", 14.00, "raisins_1kg"),
    ("Dattes Medjool 500g", "Vrac", "epicerie", "dattes-medjool-500g", "500g", 38.00, "dattes_500g"),
    ("Figues Séchées 500g", "Vrac", "epicerie", "figues-sechees-500g", "500g", 30.00, "figues_500g"),
    ("Pastèque 1kg", "Vrac", "produits-frais", "pasteque-1kg", "1kg", 4.00, "pasteque_1kg"),

    # ── VIANDE BLANCHE ───────────────────────────────────────────────────────
    # Poulet halal — produit le plus consommé au Maroc après le poisson
    # Prix de référence grande surface (kg) — souk ≈ -10 à -20 %
    ("Poulet Entier Halal 1kg", "Vrac", "produits-frais", "poulet-entier-halal-1kg", "1kg", 32.00, "poulet_entier_1kg"),
    ("Cuisses de Poulet Halal 1kg", "Vrac", "produits-frais", "cuisses-poulet-halal-1kg", "1kg", 35.00, "cuisses_poulet_1kg"),
    ("Blancs de Poulet Halal 1kg", "Vrac", "produits-frais", "blancs-poulet-halal-1kg", "1kg", 48.00, "blancs_poulet_1kg"),
    ("Dinde Hachée Halal 500g", "Vrac", "produits-frais", "dinde-hachee-halal-500g", "500g", 28.00, "dinde_hachee_500g"),
    ("Foie de Poulet 500g", "Vrac", "produits-frais", "foie-poulet-500g", "500g", 18.00, "foie_poulet_500g"),

    # ── VIANDE ROUGE ─────────────────────────────────────────────────────────
    # Viande bovine et ovine halal — consommation hebdomadaire courante au Maroc
    ("Viande Hachée Bœuf 500g", "Vrac", "produits-frais", "viande-hachee-boeuf-500g", "500g", 45.00, "viande_hachee_500g"),
    ("Kefta Bœuf Halal 500g", "Vrac", "produits-frais", "kefta-boeuf-halal-500g", "500g", 42.00, "kefta_500g"),
    ("Côtelettes Agneau 1kg", "Vrac", "produits-frais", "cotelettes-agneau-1kg", "1kg", 115.00, "cotelettes_agneau_1kg"),
    ("Merguez Bœuf Halal 500g", "Vrac", "produits-frais", "merguez-boeuf-halal-500g", "500g", 40.00, "merguez_500g"),
    ("Escalope de Veau Halal 500g", "Vrac", "produits-frais", "escalope-veau-halal-500g", "500g", 58.00, "escalope_veau_500g"),

    # ── PAIN & VIENNOISERIE ──────────────────────────────────────────────────
    # Le khobz est fait maison (farine déjà présente), le pain de mie est acheté
    ("Pain de Mie Complet 500g", "Harry's", "epicerie", "harrys-pain-mie-complet-500g", "500g", 12.90, "pain_mie_500g"),
    ("Pain de Mie Blanc 500g", "Harry's", "epicerie", "harrys-pain-mie-blanc-500g", "500g", 11.50, "pain_mie_blanc_500g"),
    ("Biscottes Heudebert 40 tranches", "Heudebert", "epicerie", "heudebert-40-tranches", "40 tranches", 18.90, "biscottes_40"),
    ("Levure de Boulanger Instantanée 11g", "Saf-Instant", "epicerie", "saf-instant-11g", "11g", 3.50, "levure_boulanger_11g"),

    # ── ŒUFS ─────────────────────────────────────────────────────────────────
    # Un des aliments les plus consommés au Maroc — protéine économique universelle
    ("Œufs Frais Catégorie A 12 pcs", "Vrac", "produits-frais", "oeufs-frais-12", "12 pcs", 22.00, "oeufs_12"),
    ("Œufs Frais Catégorie A 6 pcs", "Vrac", "produits-frais", "oeufs-frais-6", "6 pcs", 12.00, "oeufs_6"),

    # ── LÉGUMINEUSES — base de la harira, bissara, couscous ──────────────────
    ("Pois Chiches Secs 1kg", "Vrac", "epicerie", "pois-chiches-secs-1kg", "1kg", 14.00, "pois_chiches_1kg"),
    ("Lentilles Vertes 1kg", "Vrac", "epicerie", "lentilles-vertes-1kg", "1kg", 11.00, "lentilles_1kg"),
    ("Haricots Blancs Secs 1kg", "Vrac", "epicerie", "haricots-blancs-1kg", "1kg", 10.00, "haricots_blancs_1kg"),
    ("Fèves Séchées Bissara 500g", "Vrac", "epicerie", "feves-bissara-500g", "500g", 8.50, "feves_500g"),
    ("Vermicelles Safra 500g", "Safra", "epicerie", "safra-vermicelles-500g", "500g", 6.00, "vermicelles_500g"),

    # ── ÉPICES MAROCAINES — âme de la cuisine marocaine ──────────────────────
    # Sans épices, pas de tagine, harira, couscous ni méchoui
    ("Cumin Moulu 100g", "Vrac", "epicerie", "cumin-moulu-100g", "100g", 8.00, "cumin_100g"),
    ("Paprika Doux 100g", "Vrac", "epicerie", "paprika-doux-100g", "100g", 7.50, "paprika_100g"),
    ("Ras el Hanout 100g", "Vrac", "epicerie", "ras-el-hanout-100g", "100g", 14.00, "ras_el_hanout_100g"),
    ("Gingembre Moulu 100g", "Vrac", "epicerie", "gingembre-moulu-100g", "100g", 9.00, "gingembre_100g"),
    ("Curcuma 100g", "Vrac", "epicerie", "curcuma-100g", "100g", 8.00, "curcuma_100g"),
    ("Cannelle Moulue 100g", "Vrac", "epicerie", "cannelle-moulue-100g", "100g", 9.00, "cannelle_100g"),
    ("Safran Filaments 1g", "Vrac", "epicerie", "safran-1g", "1g", 15.00, "safran_1g"),
    ("Poivre Noir Moulu 100g", "Vrac", "epicerie", "poivre-noir-100g", "100g", 13.00, "poivre_100g"),
    ("Sel Fin 1kg", "Vrac", "epicerie", "sel-fin-1kg", "1kg", 4.00, "sel_1kg"),

    # ── CONDIMENTS & CONSERVES TYPIQUES ──────────────────────────────────────
    ("Olives Beldi Marinées 500g", "Vrac", "epicerie", "olives-beldi-500g", "500g", 16.00, "olives_500g"),
    ("Citrons Confits Bocal 500g", "Aïcha", "epicerie", "aicha-citrons-confits-500g", "500g", 22.00, "citrons_confits_500g"),
    ("Confiture Abricot Aïcha 370g", "Aïcha", "epicerie", "aicha-confiture-abricot-370g", "370g", 19.90, "confiture_abricot_370g"),
    ("Confiture Fraise Aïcha 370g", "Aïcha", "epicerie", "aicha-confiture-fraise-370g", "370g", 18.50, "confiture_fraise_370g"),
    ("Amlou Pâte Amande Argan 200g", "Vrac", "epicerie", "amlou-200g", "200g", 45.00, "amlou_200g"),

    # ── MIEL — présent sur chaque table marocaine ─────────────────────────────
    ("Miel d'Euphorbe 500g", "Vrac", "epicerie", "miel-euphorbe-500g", "500g", 55.00, "miel_500g"),
    ("Miel de Thym 250g", "Vrac", "epicerie", "miel-thym-250g", "250g", 38.00, "miel_thym_250g"),

    # ── POISSON FRAIS ─────────────────────────────────────────────────────────
    # Maroc = 1er producteur halieutique d'Afrique — sardines = protéine du quotidien
    ("Sardines Fraîches 1kg", "Vrac", "produits-frais", "sardines-fraiches-1kg", "1kg", 15.00, "sardines_fraiches_1kg"),
    ("Sole Fraîche 1kg", "Vrac", "produits-frais", "sole-fraiche-1kg", "1kg", 55.00, "sole_fraiche_1kg"),
    ("Crevettes Fraîches 500g", "Vrac", "produits-frais", "crevettes-fraiches-500g", "500g", 45.00, "crevettes_500g"),

    # ── HUILE D'OLIVE — patrimoine marocain ────────────────────────────────────
    ("Huile d'Olive Extra Vierge Moulins 1L", "Moulins de la Médina", "epicerie",
     "moulins-medina-olive-1l", "1L", 95.00, "huile_olive_1l"),

    # ── BÉBÉ ────────────────────────────────────────────────────────────────
    ("Couches Pampers Premium T3 52 pcs", "Pampers", "bebe", "pampers-premium-t3-52", "52 pcs", 129.00, "pampers_t3_52"),
    ("Lait 1er Âge Blédina 400g", "Blédina", "bebe", "bledina-1er-age-400g", "400g", 89.00, "bledina_400g"),
    ("Lingettes WaterWipes 60 pcs", "WaterWipes", "bebe", "waterwipes-60", "60 pcs", 54.90, "waterwipes_60"),
]

# Catégories → IDs en base
CATEGORY_MAP = {
    "epicerie": 1,
    "produits-frais": 2,
    "boissons": 3,
    "hygiene-beaute": 4,
    "entretien": 5,
    "bebe": 6,
}

# Stores → IDs en base et facteurs de prix
STORES = {
    1: {"name": "Marjane", "factor": 1.0},      # prix de référence
    2: {"name": "Carrefour", "factor": 1.05},   # légèrement plus cher
    3: {"name": "Label'Vie", "factor": 1.03},   # prix intermédiaire
    4: {"name": "BIM", "factor": 0.88},         # discount (moins cher)
    5: {"name": "Atacadão", "factor": 0.93},    # format entrepôt
}

def slugify(text: str) -> str:
    text = text.lower().strip()
    for fr, en in [("à", "a"), ("â", "a"), ("ä", "a"), ("é", "e"), ("è", "e"), ("ê", "e"),
                   ("ë", "e"), ("î", "i"), ("ï", "i"), ("ô", "o"), ("ö", "o"), ("ù", "u"),
                   ("û", "u"), ("ü", "u"), ("ç", "c"), ("'", "-"), ("'", "-")]:
        text = text.replace(fr, en)
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = re.sub(r"-+", "-", text).strip("-")
    return text[:490]


async def seed():
    print("Connexion à la base de données...")
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Supprimer les données existantes
        print("Suppression des données existantes...")
        await conn.execute("DELETE FROM price_alerts")
        await conn.execute("DELETE FROM shopping_list_items")
        await conn.execute("DELETE FROM prices")
        await conn.execute("DELETE FROM products")

        count_products = 0
        count_prices = 0

        print(f"Insertion de {len(PRODUCTS)} produits avec prix pour 5 magasins...")

        for (name, brand, cat_slug, img_key, unit, ref_price, product_key) in PRODUCTS:
            slug = slugify(name)
            category_id = CATEGORY_MAP.get(cat_slug, 1)
            image_url = f"https://images.prixmaroc.ma/products/{img_key}.jpg"

            # Insérer le produit
            product_id = await conn.fetchval(
                """INSERT INTO products (name, slug, brand, image_url, unit, category_id, is_active)
                   VALUES ($1, $2, $3, $4, $5, $6, TRUE)
                   ON CONFLICT (slug) DO UPDATE SET brand=EXCLUDED.brand, updated_at=NOW()
                   RETURNING id""",
                name, slug, brand, image_url, unit, category_id
            )
            count_products += 1

            # Insérer les prix pour chaque magasin avec historique (6 mois)
            for store_id, store_info in STORES.items():
                factor = store_info["factor"]
                base_price = round(ref_price * factor, 2)

                # Ajouter de la variabilité par produit pour que ce soit réaliste
                product_variation = random.uniform(0.96, 1.04)
                store_price = round(base_price * product_variation, 2)
                # Arrondir aux 0.50 DH les plus proches (prix typiques au Maroc)
                store_price = round(store_price * 2) / 2

                # Prix actuel
                is_promo = random.random() < 0.20  # 20% chance de promo
                promo_price = round(store_price * random.uniform(0.80, 0.92), 2) if is_promo else None

                await conn.execute(
                    """INSERT INTO prices (product_id, store_id, price, currency, is_promo, promo_price, source, recorded_at)
                       VALUES ($1, $2, $3, 'MAD', $4, $5, 'scraper', NOW())""",
                    product_id, store_id, store_price, is_promo, promo_price
                )
                count_prices += 1

                # Historique des 6 derniers mois (un prix par mois)
                for months_ago in [6, 5, 4, 3, 2, 1]:
                    # Les prix varient légèrement dans le temps (inflation ~5%/an au Maroc)
                    inflation_factor = 1 + (months_ago * 0.004)  # ~0.4% par mois
                    hist_price = round(store_price / inflation_factor * random.uniform(0.97, 1.03), 2)
                    hist_price = round(hist_price * 2) / 2
                    record_date = datetime.now(timezone.utc) - timedelta(days=months_ago * 30)

                    await conn.execute(
                        """INSERT INTO prices (product_id, store_id, price, currency, is_promo, source, recorded_at)
                           VALUES ($1, $2, $3, 'MAD', FALSE, 'scraper', $4)""",
                        product_id, store_id, hist_price, record_date
                    )
                    count_prices += 1

        # Stats
        final_products = await conn.fetchval("SELECT COUNT(*) FROM products")
        final_prices = await conn.fetchval("SELECT COUNT(*) FROM prices")

        print(f"\n{'='*60}")
        print(f"SEED TERMINÉ:")
        print(f"  Produits insérés: {count_products} → Total: {final_products}")
        print(f"  Prix insérés:     {count_prices} → Total: {final_prices}")
        print(f"{'='*60}")

        # Afficher un aperçu
        sample = await conn.fetch("""
            SELECT p.name, p.brand, s.name as store_name, pr.price, pr.is_promo
            FROM products p
            JOIN prices pr ON pr.product_id = p.id
            JOIN stores s ON s.id = pr.store_id
            WHERE pr.recorded_at > NOW() - INTERVAL '1 hour'
            ORDER BY p.name, s.name
            LIMIT 20
        """)
        print("\nAperçu des prix:")
        for row in sample:
            promo = " [PROMO]" if row['is_promo'] else ""
            print(f"  {row['name'][:40]:40s} | {row['store_name']:12s} | {row['price']:6.2f} DH{promo}")

    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(seed())
