"""
Reconnaître qu'un relevé désigne un produit déjà connu.

Le collecteur rapprochait un relevé d'un produit par égalité exacte du nom.
Or le nom est réécrit à chaque passage par le modèle qui relit le catalogue :
il place la marque tantôt dans le nom, tantôt dans le champ dédié, et écrit
« (1 kg) », « 1kg » ou rien. La moindre variation créait un produit de plus,
et l'historique d'un même article se brisait en autant de courbes.

    #1291  Rondelles de poulet croustillantes LEZITA
    #305   Rondelles de poulet croustillantes LEZITA (1 kg)

Le piège est symétrique : deux noms très proches peuvent désigner deux
produits bien distincts, et les confondre serait pire que de les séparer.

    #785  Mortadelle nature 600 g
    #786  Mortadelle nature 300 g

D'où la règle : la contenance fait partie de l'identité et n'est jamais
ignorée, mais tout le reste — accents, ponctuation, casse, place de la
marque, « 1 kg » contre « 1kg » — est neutralisé.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# Vers une unité commune : « 1 kg » et « 1000 g » sont la même contenance.
_VERS_GRAMMES = {"kg": 1000.0, "g": 1.0, "gr": 1.0, "mg": 0.001}
_VERS_MILLILITRES = {"l": 1000.0, "cl": 10.0, "ml": 1.0, "dl": 100.0}

# « 500 g », « 1,5L », « 33 cl », « 5 Litres » — l'unité peut être écrite en
# toutes lettres : sans ces formes, « 1 Litre » passait pour une contenance
# inconnue et se confondait avec n'importe quelle autre.
_UNITES = (
    r"kilogrammes?|kilos?|kg|grammes?|gr|g|mg"
    r"|centilitres?|cl|millilitres?|ml|decilitres?|dl|litres?|l"
)
_MOTIF_MESURE = re.compile(
    rf"(?<![a-z0-9])(\d+(?:[.,]\d+)?)\s*({_UNITES})(?![a-z0-9])"
)
_FAMILLE_UNITE = {
    "kilogramme": "kg", "kilogrammes": "kg", "kilo": "kg", "kilos": "kg", "kg": "kg",
    "gramme": "g", "grammes": "g", "gr": "g", "g": "g", "mg": "mg",
    "centilitre": "cl", "centilitres": "cl", "cl": "cl",
    "millilitre": "ml", "millilitres": "ml", "ml": "ml",
    "decilitre": "dl", "decilitres": "dl", "dl": "dl",
    "litre": "l", "litres": "l", "l": "l",
}
# « x6 », « 6 pièces », « lot de 4 », « paquet de 54 »
_MOTIF_NOMBRE = re.compile(
    r"(?<![a-z0-9])(?:x\s*(\d+)"
    r"|(\d+)\s*(?:pieces?|portions?|pcs?|pc|unites?|sachets?|capsules?|rouleaux?)"
    r"|(?:lot|pack|paquet|boite|boites)\s+de\s+(\d+))(?![a-z0-9])"
)


def sans_accents(texte: str) -> str:
    t = texte.lower().replace("œ", "oe").replace("æ", "ae")
    t = unicodedata.normalize("NFKD", t)
    return "".join(c for c in t if not unicodedata.combining(c))


@dataclass(frozen=True)
class Empreinte:
    """
    Ce qui identifie un produit, indépendamment de la façon de l'écrire.

    `base_seule` est le nom débarrassé de la marque, `base_complete` le garde :
    un produit enregistré sans champ marque porte la sienne dans son nom, et
    seule la comparaison des deux formes permet de les rapprocher.

    La marque est conservée à part parce qu'elle appartient à l'identité. Une
    première version comparait les noms démarqués des deux côtés : tous les
    « gel douche » se confondaient alors en un seul produit, NIVEA avec FA.
    """
    base_seule: str
    base_complete: str
    contenance: str | None     # « 1000g », « 330ml », « 6u » — ou None si non dite
    marque: str                # normalisée, vide si inconnue


def _contenance(texte: str, format_: str | None) -> str | None:
    """Contenance canonique, lue dans le nom puis, à défaut, dans le format."""
    for source in (texte, sans_accents(format_ or "")):
        if not source:
            continue
        mesure = _MOTIF_MESURE.search(source)
        if mesure:
            valeur = float(mesure.group(1).replace(",", "."))
            unite = _FAMILLE_UNITE[mesure.group(2)]
            if unite in _VERS_GRAMMES:
                return f"{valeur * _VERS_GRAMMES[unite]:.0f}g"
            return f"{valeur * _VERS_MILLILITRES[unite]:.0f}ml"

        nombre = _MOTIF_NOMBRE.search(source)
        if nombre:
            quantite = next(g for g in nombre.groups() if g)
            return f"{int(quantite)}u"
    return None


def _nettoyer(texte: str) -> str:
    sans_mesure = _MOTIF_MESURE.sub(" ", texte)
    sans_nombre = _MOTIF_NOMBRE.sub(" ", sans_mesure)
    return " ".join(re.sub(r"[^a-z0-9]+", " ", sans_nombre).split())


def _retirer(base: str, marque: str) -> str:
    """Le nom privé des mots de la marque, où qu'ils soient placés."""
    reste = base
    for mot in marque.split():
        reste = re.sub(rf"(?<![a-z0-9]){re.escape(mot)}(?![a-z0-9])", " ", reste)
    return " ".join(reste.split())


def _porte_la_marque(base: str, marque: str) -> bool:
    """Le nom contient-il tous les mots de la marque ?"""
    mots = set(base.split())
    return bool(marque) and all(mot in mots for mot in marque.split())


def empreinte(nom: str, marque: str | None = None, format_: str | None = None) -> Empreinte:
    brut = sans_accents(nom)
    contenance = _contenance(brut, format_)
    complete = _nettoyer(brut)
    # La marque peut être écrite autrement dans le nom (« San Mateo » contre
    # « SAN MATEO ») : on la normalise comme le reste avant de la retirer.
    marque_nette = _nettoyer(sans_accents(marque)) if marque else ""
    seule = _retirer(complete, marque_nette) if marque_nette else complete

    return Empreinte(
        base_seule=seule or complete,
        base_complete=complete,
        contenance=contenance,
        marque=marque_nette,
    )


def _contenances_compatibles(a: str | None, b: str | None) -> bool:
    """
    Une contenance absente d'un côté ne sépare pas : « Rondelles LEZITA » et
    « Rondelles LEZITA 1 kg » sont le même article, l'un simplement moins
    précis. Deux contenances dites et différentes, en revanche, séparent.
    """
    return a is None or b is None or a == b


def correspondent(a: Empreinte, b: Empreinte) -> bool:
    """
    Les deux empreintes désignent-elles le même article ?

    La marque commande. Deux marques connues et différentes séparent, même
    sous un nom identique : « Gel douche NIVEA » n'est pas « Gel douche FA ».

    Quand une seule marque est connue, on n'accepte le rapprochement que si
    l'autre nom la porte en toutes lettres. Sans cette exigence, un produit
    vague comme « Lingettes bébé » aurait servi de point de ralliement à
    LOVELY BABIES et à DODOT, qu'il aurait fini par confondre.
    """
    if not _contenances_compatibles(a.contenance, b.contenance):
        return False

    if a.marque and b.marque:
        if a.marque != b.marque:
            return False
        return a.base_seule == b.base_seule or a.base_complete == b.base_complete

    if a.marque or b.marque:
        connue, autre = (a, b) if a.marque else (b, a)
        if not _porte_la_marque(autre.base_complete, connue.marque):
            return False
        return connue.base_seule == _retirer(autre.base_complete, connue.marque)

    return a.base_complete == b.base_complete


class IndexProduits:
    """
    Les produits connus, interrogeables par empreinte.

    Le catalogue tient en quelques centaines de lignes : on le charge une fois
    par collecte plutôt que d'interroger la base à chaque relevé.
    """

    def __init__(self) -> None:
        self._entrees: list[tuple[Empreinte, int]] = []

    def ajouter(self, produit_id: int, nom: str, marque: str | None, format_: str | None) -> None:
        self._entrees.append((empreinte(nom, marque, format_), produit_id))

    def trouver(self, nom: str, marque: str | None, format_: str | None) -> int | None:
        """
        Identifiant du produit correspondant, ou None.

        Une contenance exacte l'emporte sur une correspondance obtenue grâce à
        une contenance absente : sans cette préférence, un relevé « Mortadelle
        nature » sans poids pourrait se greffer sur le 600 g alors que le
        300 g existe aussi.
        """
        cible = empreinte(nom, marque, format_)
        approximatif: int | None = None

        for connue, produit_id in self._entrees:
            if not correspondent(connue, cible):
                continue
            if connue.contenance is not None and connue.contenance == cible.contenance:
                return produit_id
            if approximatif is None:
                approximatif = produit_id

        return approximatif

    def __len__(self) -> int:
        return len(self._entrees)
