"""
liste_courses.py — Outils de traduction du plan nutritionnel en produits.

Le générateur de liste choisit, pour chaque besoin du plan (« 13 kg de
farine », « 17 L de lait »), un produit du catalogue et une quantité. Trois
erreurs rendaient les listes absurdes :

1. Recherche par fragment : le mot-clé « bahia » prévu pour l'eau attrapait
   « Couscous Bahia », et « sucre » attrapait « Biscuits sans sucre ».
2. Taille des paquets ignorée : 17 L de lait devenaient 17 packs de 6 L.
3. Produits frais absents des catalogues de supermarché (légumes, fruits,
   viande, œufs) : la ligne disparaissait en silence.

Ce module fournit la recherche par mot entier avec contrôle du type de
produit, la lecture de la contenance, et des prix indicatifs pour les
produits qu'aucun catalogue ne couvre.
"""
from __future__ import annotations

import math
import re
import unicodedata
from dataclasses import dataclass


def normaliser(texte: str) -> str:
    """Minuscules, sans accents, « œ » développé : « Œufs » → « oeufs »."""
    t = texte.lower().replace("œ", "oe").replace("æ", "ae")
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


def contient_mot(nom: str, terme: str) -> bool:
    """
    Le terme apparaît-il en mots entiers ? Pluriel toléré sur chaque mot,
    en s comme en x (« maquereaux »).

    « sucre » ne reconnaît donc pas « sans sucre » comme un sucre — ce cas est
    traité par le contrôle de type — mais surtout « ail » ne reconnaît plus
    « travail », ni « eau » « chapeau ».
    """
    n, t = normaliser(nom), normaliser(terme).strip()
    if not t:
        return False
    motif = r"\s+".join(re.escape(m) + "(?:s|x)?" for m in t.split())
    return re.search(rf"(?<![a-z0-9]){motif}(?![a-z])", n) is not None


# Noms de familles de produits. Un candidat qui porte une famille absente du
# besoin est écarté : « Couscous Bahia » n'est pas de l'eau, « Biscuits sans
# sucre » n'est pas du sucre.
FAMILLES = (
    "couscous", "farine", "semoule", "riz", "pates", "spaghetti", "penne",
    "vermicelle", "lait", "yaourt", "fromage", "beurre", "margarine", "huile",
    "sucre", "the", "cafe", "sel", "lentille", "pois chiche", "haricot",
    "feve", "thon", "sardine", "maquereau", "confiture", "miel", "olive",
    "eau", "jus", "levure", "harissa", "concentre", "biscuit", "gaufrette",
    "chocolat", "cereale", "cake", "boisson", "soda", "pain", "epice",
    # Leurres : produits transformés qui empruntent le nom d'un aliment.
    "noodle", "nouille", "chips", "soupe", "sauce", "bouillon", "snack",
)

# Ce qui ne se mange pas, même si le nom contient un mot d'aliment.
NON_ALIMENTAIRE = (
    "cologne", "chauffe", "javel", "parfum", "amande douce", "cloche",
    "shampooing", "savon", "gel douche", "creme", "lotion",
)


# Mentions qui changent la nature d'un produit, où qu'elles soient dans le nom :
# des « vermicelles chocolat » ne vont pas dans la harira, un « beurre de
# cacahuète » n'est pas du beurre.
LEURRES = (
    "chocolat", "cacao", "beurre de cacahuete", "biscuit", "gaufrette", "cake",
    "noodle", "nouille", "chips", "soupe", "sauce", "bouillon", "snack",
)


def familles_de(texte: str) -> set[str]:
    return {f for f in FAMILLES if contient_mot(texte, f)}


def famille_principale(nom: str) -> str | None:
    """
    Famille du nom principal : la première qui apparaît.

    En français le nom principal vient en tête — « Biscuits sans sucre » est
    un biscuit, « Thon à l'huile » est du thon. Retenir n'importe quelle
    famille présente ferait passer le biscuit pour du sucre.
    """
    n = normaliser(nom)
    meilleure: tuple[int, str] | None = None
    for f in FAMILLES:
        motif = r"\s+".join(re.escape(m) + "(?:s|x)?" for m in f.split())
        m = re.search(rf"(?<![a-z0-9]){motif}(?![a-z])", n)
        if m and (meilleure is None or m.start() < meilleure[0]):
            meilleure = (m.start(), f)
    return meilleure[1] if meilleure else None


def candidat_acceptable(nom_produit: str, besoin: str, mots_cles: list[str],
                        alimentaire: bool = True) -> bool:
    """Le produit correspond-il à la famille du besoin ?"""
    if alimentaire and any(contient_mot(nom_produit, x) for x in NON_ALIMENTAIRE):
        return False
    attendues = familles_de(besoin.split("(")[0]) | set().union(
        *(familles_de(k) for k in mots_cles)
    )
    demande = " ".join([besoin, *mots_cles])
    if any(contient_mot(nom_produit, l) and not contient_mot(demande, l) for l in LEURRES):
        return False
    principale = famille_principale(nom_produit)
    # Un produit sans famille reconnue (« Sidi Ali 1,5 L ») est admis : c'est
    # le mot-clé, précis, qui l'a désigné.
    return principale is None or principale in attendues


_UNITES = {"kg": 1.0, "g": 0.001, "l": 1.0, "cl": 0.01, "ml": 0.001}


def contenance(nom: str, format_: str | None = None) -> float | None:
    """
    Quantité totale d'un article, en kg ou en litres.

    « Lait UHT 1 L × 6 » → 6.0 · « 500ml x6 » → 3.0 · « Beurre 100 g » → 0.1.
    None quand le nom ne dit rien : l'appelant retombe alors sur un compte
    d'unités.
    """
    texte = normaliser(f"{nom} {format_ or ''}").replace(",", ".")
    m = re.search(r"(\d+(?:\.\d+)?)\s*(kg|g|cl|ml|l)(?![a-z])", texte)
    if not m:
        return None
    base = float(m.group(1)) * _UNITES[m.group(2)]

    # Multiplicateur écrit avant (« 6 x 1 L ») ou après (« 1 L × 6 »).
    avant = texte[:m.start()]
    apres = texte[m.end():]
    mult = 1
    m2 = re.search(r"(?:x|×)\s*(\d{1,2})(?!\d)", apres[:8]) or \
         re.search(r"(\d{1,2})\s*(?:x|×)\s*$", avant[-8:])
    if m2:
        mult = int(m2.group(1))
    total = base * mult
    return total if total >= 0.005 else None


def prix_de_reference(prix: float, nom: str, format_: str | None) -> tuple[int, float]:
    """
    Clé de tri des candidats : prix au kilo ou au litre quand la contenance
    est lisible, sinon prix à l'article.

    Trier sur le prix à l'article fait gagner le plus petit format : 60
    bouteilles de 50 cl au lieu de 6 packs de 5 L. Les articles de contenance
    connue passent devant, puisqu'eux seuls se comparent honnêtement.
    """
    c = contenance(nom, format_)
    return (0, prix / c) if c else (1, prix)


def nombre_d_unites(besoin: float, nom: str, format_: str | None) -> int:
    """Nombre d'articles à acheter pour couvrir un besoin en kg ou en litres."""
    c = contenance(nom, format_)
    if c:
        return max(1, math.ceil(besoin / c - 0.15))   # tolérance : pas un pack pour 150 g
    return max(1, round(besoin))


@dataclass(frozen=True)
class PrixIndicatif:
    nom: str
    prix: float          # DH par unité de vente
    unite: str           # « kg », « pièce », « botte »
    poids_unite: float   # kg par unité de vente (1 pour le kg)
    rayon: str           # « souk » ou « épicerie »


# Estimations de prix courants au Maroc (septembre 2026) pour ce qu'aucun
# catalogue de supermarché ne propose. Ce ne sont PAS des relevés : la liste
# les présente comme indicatifs, et les relevés du souk faits par les
# utilisateurs ont vocation à les remplacer.
PRIX_INDICATIFS: dict[str, PrixIndicatif] = {
    "Œufs frais":        PrixIndicatif("Œufs frais", 1.4, "pièce", 0.06, "souk"),
    "Sel fin":           PrixIndicatif("Sel fin", 3.0, "kg", 1.0, "épicerie"),
    "Sucre":             PrixIndicatif("Sucre", 7.5, "kg", 1.0, "épicerie"),
    "Tomates fraîches":  PrixIndicatif("Tomates", 7.0, "kg", 1.0, "souk"),
    "Oignons":           PrixIndicatif("Oignons", 6.0, "kg", 1.0, "souk"),
    "Pommes de terre":   PrixIndicatif("Pommes de terre", 6.0, "kg", 1.0, "souk"),
    "Carottes":          PrixIndicatif("Carottes", 5.0, "kg", 1.0, "souk"),
    "Ail":               PrixIndicatif("Ail", 35.0, "kg", 1.0, "souk"),
    "Herbes fraîches":   PrixIndicatif("Persil et coriandre", 2.0, "botte", 0.1, "souk"),
    "Sardines fraîches": PrixIndicatif("Sardines fraîches", 18.0, "kg", 1.0, "souk"),
    "Sardines en boîte": PrixIndicatif("Sardines en boîte (125 g)", 5.0, "boîte", 0.125, "épicerie"),
    "Courgettes":        PrixIndicatif("Courgettes", 7.0, "kg", 1.0, "souk"),
    "Poivrons":          PrixIndicatif("Poivrons", 9.0, "kg", 1.0, "souk"),
    "Aubergines":        PrixIndicatif("Aubergines", 7.0, "kg", 1.0, "souk"),
    "Légumes verts":     PrixIndicatif("Haricots verts", 12.0, "kg", 1.0, "souk"),
    "Oranges":           PrixIndicatif("Oranges", 7.0, "kg", 1.0, "souk"),
    "Bananes":           PrixIndicatif("Bananes", 15.0, "kg", 1.0, "souk"),
    "Cuisses de poulet": PrixIndicatif("Poulet (cuisses)", 30.0, "kg", 1.0, "souk"),
    "Pommes (":          PrixIndicatif("Pommes", 14.0, "kg", 1.0, "souk"),
    "Dattes":            PrixIndicatif("Dattes", 50.0, "kg", 1.0, "souk"),
    "Viande hachée":     PrixIndicatif("Viande hachée de bœuf", 110.0, "kg", 1.0, "souk"),
    "Merguez":           PrixIndicatif("Merguez", 90.0, "kg", 1.0, "souk"),
    "Agneau":            PrixIndicatif("Agneau", 120.0, "kg", 1.0, "souk"),
    "Dinde":             PrixIndicatif("Dinde", 60.0, "kg", 1.0, "souk"),
    "Sole":              PrixIndicatif("Poisson (sole)", 90.0, "kg", 1.0, "souk"),
    "Cumin":             PrixIndicatif("Cumin moulu (100 g)", 12.0, "sachet", 0.1, "épicerie"),
    "Paprika":           PrixIndicatif("Paprika doux (100 g)", 9.0, "sachet", 0.1, "épicerie"),
    "Ras el Hanout":     PrixIndicatif("Ras el hanout (100 g)", 15.0, "sachet", 0.1, "épicerie"),
    "Harissa":           PrixIndicatif("Harissa (pot de 135 g)", 8.0, "pot", 0.135, "épicerie"),
}


def prix_indicatif(besoin: str) -> PrixIndicatif | None:
    for prefixe, ref in PRIX_INDICATIFS.items():
        if besoin.startswith(prefixe):
            return ref
    return None


def quantite_vendue(besoin_kg: float, ref: PrixIndicatif) -> float:
    """Arrondi au pas de vente : demi-kilo, pièce ou botte."""
    if ref.unite == "kg":
        return max(0.5, round(besoin_kg * 2) / 2)
    return float(max(1, math.ceil(besoin_kg / ref.poids_unite - 0.15)))
