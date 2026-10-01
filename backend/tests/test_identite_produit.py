"""
Tests de l'identité produit.

Les cas proviennent du catalogue réel : chaque paire « à fusionner » est un
doublon observé en base, chaque paire « à séparer » est une distinction que
la correction ne doit pas détruire.
"""
import pytest

from app.services.identite_produit import IndexProduits, correspondent, empreinte


# (nom A, marque A, format A), (nom B, marque B, format B)
A_FUSIONNER = [
    # Même marque des deux côtés, mais écrite dans le nom une fois sur deux.
    # C'est le cas dominant en base.
    (("Pack Brownie au chocolat BE", "BE", "5 x 40 g"),
     ("Pack Brownie au chocolat", "BE", "5 x 40 g")),
    (("Boisson végétale à l'amande DOST", "DOST", "1 L"),
     ("Boisson végétale à l'amande", "DOST", "1 L")),
    (("Mix d'orge, chicorée et café VIP", "VIP", "100 g"),
     ("Mix d'orge, chicorée et café", "VIP", "100 g")),
    (("Mini pains suisses surgelés CHOPAIN", "CHOPAIN", "6 pièces"),
     ("Mini pains suisses surgelés", "CHOPAIN", "6 pièces")),
    # Marque connue d'un seul côté, mais présente dans l'autre nom.
    (("Rondelles de poulet croustillantes LEZITA (1 kg)", None, None),
     ("Rondelles de poulet croustillantes LEZITA", "LEZITA", "1 kg")),
    (("Crevettes grises SAN MATEO 2Kg", None, None),
     ("Crevettes grises San Mateo", "San Mateo", "2 kg")),
    # Aucune marque renseignée : le nom complet fait foi.
    (("Margarine Ledda", None, None),
     ("Margarine Ledda 5 kg", None, None)),
    # Accents de la marque.
    (("Eau minérale naturelle AÏN SAÏSS", "AÏN SAÏSS", "1,5 L"),
     ("Eau minérale naturelle", "AIN SAISS", "1,5 litre")),
    # Écriture de la contenance.
    (("Fromage blanc Le Berger 900g", "Le Berger", None),
     ("Fromage blanc Le Berger 900 g", "Le Berger", None)),
    (("Huile de table Lesieur 1 L", "Lesieur", None),
     ("Huile de table Lesieur 100 cl", "Lesieur", None)),
    # Contenance portée par le champ format plutôt que par le nom.
    (("Couscous Dari", "Dari", "1kg"),
     ("Couscous Dari 1 kg", "Dari", None)),
    # Ligature et ponctuation.
    (("Œufs frais calibre moyen", None, "x30"),
     ("Oeufs frais calibre moyen", None, "30 pièces")),
]

A_SEPARER = [
    # Deux contenances dites et différentes : deux produits.
    (("Mortadelle nature 600 g", None, None),
     ("Mortadelle nature 300 g", None, None)),
    (("Fromage blanc Le Berger 200 g", "Le Berger", None),
     ("Fromage blanc Le Berger 900g", "Le Berger", None)),
    (("Détergent machine BILL MATIC (9 kg)", "BILL MATIC", None),
     ("Détergent machine Bill Matic 750 g", "Bill Matic", None)),
    (("Lait Jaouda 1 L", "Jaouda", None),
     ("Lait Jaouda 50 cl", "Jaouda", None)),
    # Produits simplement différents.
    (("Thon à l'huile Titus", "Titus", None),
     ("Thon à la tomate Titus", "Titus", None)),
    (("Yaourt nature Danone", "Danone", None),
     ("Yaourt fraise Danone", "Danone", None)),

    # ── Fausses fusions observées, que la marque doit empêcher ──────────────
    # Même nom générique, deux marques : deux produits.
    (("Gel douche FA", "FA", "250 ml"),
     ("Gel Douche NIVEA", "NIVEA", "250ml")),
    (("Riz basmati Akka", "Akka", "1 kg"),
     ("Riz Basmati Tavish", "Tavish", "1 kg")),
    (("Serviettes hygiéniques SCARLETT", "SCARLETT", None),
     ("Serviettes hygiéniques MIA", "MIA", None)),
    (("Fromage fondu Jibal", "Jibal", "64 pièces"),
     ("Fromage fondu El Mejor", "El Mejor", "64 portions")),
    (("Eau de javel LA CROIX", "LA CROIX", "4 litres"),
     ("Eau de Javel Dimex", "Dimex", "5 Litres")),
    # Unité écrite en toutes lettres : « 5 Litres » n'est pas « 33 cl ».
    (("Eau de Table AQUAFINA", "AQUAFINA", "5 Litres"),
     ("Eau de table Amane", "Amane", "33 cl")),
    (("Nectar Rostoy pêche", "Rostoy", "33 cl"),
     ("Nectar Pêche", "ROSTOY", "1 Litre")),
    # Un produit sans marque ne doit pas servir de point de ralliement à deux
    # marques différentes : il reste à l'écart des deux.
    (("Lingettes bébé", None, None),
     ("Lingettes Bébé LOVELY BABIES", "LOVELY BABIES", "72 pièces")),
    (("Lingettes bébé", None, None),
     ("Lingettes Bébé DODOT", "DODOT", "Paquet de 54")),
]


@pytest.mark.parametrize("a, b", A_FUSIONNER)
def test_reconnait_le_meme_produit(a, b):
    assert correspondent(empreinte(*a), empreinte(*b)), f"{a[0]!r} devrait rejoindre {b[0]!r}"


@pytest.mark.parametrize("a, b", A_SEPARER)
def test_distingue_deux_produits(a, b):
    assert not correspondent(empreinte(*a), empreinte(*b)), f"{a[0]!r} ne doit pas rejoindre {b[0]!r}"


def test_contenance_canonique():
    assert empreinte("Huile 1 L").contenance == "1000ml"
    assert empreinte("Huile 100cl").contenance == "1000ml"
    assert empreinte("Farine 1kg").contenance == "1000g"
    assert empreinte("Farine 1000 g").contenance == "1000g"
    assert empreinte("Œufs", format_="x30").contenance == "30u"
    assert empreinte("Couscous Dari").contenance is None


def test_contenance_en_toutes_lettres():
    """« 5 Litres » passait pour inconnu et se confondait avec tout le reste."""
    assert empreinte("Eau de table", format_="5 Litres").contenance == "5000ml"
    assert empreinte("Nectar", format_="1 Litre").contenance == "1000ml"
    assert empreinte("Farine", format_="2 kilos").contenance == "2000g"
    assert empreinte("Biscuits", format_="200 grammes").contenance == "200g"
    assert empreinte("Fromage", format_="24 portions").contenance == "24u"
    assert empreinte("Lingettes", format_="Paquet de 54").contenance == "54u"


def test_marque_retiree_du_nom():
    e = empreinte("Couscous Dari Moyen", marque="Dari")
    assert "dari" not in e.base_seule
    assert "dari" in e.base_complete


def test_index_prefere_la_contenance_exacte():
    index = IndexProduits()
    index.ajouter(1, "Mortadelle nature 600 g", None, None)
    index.ajouter(2, "Mortadelle nature 300 g", None, None)

    assert index.trouver("Mortadelle nature 300 g", None, None) == 2
    assert index.trouver("Mortadelle nature 600g", None, None) == 1


def test_index_rattache_un_releve_sans_contenance():
    index = IndexProduits()
    index.ajouter(7, "Rondelles de poulet croustillantes LEZITA (1 kg)", "LEZITA", None)

    assert index.trouver("Rondelles de poulet croustillantes LEZITA", "LEZITA", None) == 7


def test_index_ignore_un_produit_inconnu():
    index = IndexProduits()
    index.ajouter(1, "Couscous Dari 1kg", "Dari", None)

    assert index.trouver("Huile de table Lesieur 5L", "Lesieur", None) is None
