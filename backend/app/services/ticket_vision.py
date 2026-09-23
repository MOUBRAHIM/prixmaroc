"""
ticket_vision.py — Lecture d'un ticket de caisse par Claude Vision.

Tesseract, jusqu'ici seul moteur, tenait mal sur les tickets marocains :
sur un ticket d'essai net, il rendait « PAIN DE MIE 12,00 » en « PANDEMIE
1200 » et ne retrouvait qu'un article sur cinq. La virgule décimale perdue
est le pire cas : un prix devient cent fois trop grand sans que rien ne le
signale. Il mettait par ailleurs 47 secondes sur l'instance de production,
au bord du délai d'attente de l'application.

Un modèle de vision lit le ticket comme un humain : il rattache le prix à
sa ligne, comprend les abréviations d'enseigne et ne confond pas un total
avec un article. Coût observé : quelques centimes de dirham par ticket.

Tesseract reste le secours quand la clé manque ou que l'appel échoue : mieux
vaut une lecture imparfaite que pas de lecture.
"""
from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass
from datetime import date

import anthropic

from app.core.config import settings

log = logging.getLogger(__name__)

MODELE = "claude-haiku-4-5-20251001"

# Bornes de bon sens pour un article de supermarché marocain. Au-delà, c'est
# une lecture fausse — typiquement une virgule décimale perdue.
PRIX_MIN, PRIX_MAX = 0.5, 5000.0
QUANTITE_MAX = 99

CONSIGNE = """Tu lis un ticket de caisse marocain et tu en extrais les achats.

Réponds UNIQUEMENT par un objet JSON, sans commentaire ni bloc de code :
{"magasin": "...", "date": "AAAA-MM-JJ", "total": 123.45,
 "articles": [{"nom": "...", "quantite": 1, "prix_unitaire": 9.5, "prix_total": 9.5}]}

Règles :
- Les prix marocains s'écrivent avec une virgule : « 12,00 » vaut 12.00, pas 1200.
  Si un montant paraît cent fois trop grand pour l'article, c'est une virgule
  manquante — rétablis-la.
- N'inscris PAS le total du ticket, la TVA, le rendu de monnaie ni le mode de
  paiement parmi les articles. Le total va dans le champ « total ».
- "quantite" vaut 1 si le ticket ne précise rien.
- "prix_total" est ce qui est facturé pour la ligne ; "prix_unitaire" = prix_total / quantite.
- Corrige les abréviations évidentes du ticket en mots lisibles, sans inventer
  de marque absente.
- "magasin", "date" et "total" valent null si le ticket ne les montre pas.
- Si l'image n'est pas un ticket de caisse, réponds {"articles": []}."""


@dataclass(frozen=True)
class Article:
    nom: str
    quantite: float
    prix_unitaire: float
    prix_total: float


@dataclass(frozen=True)
class Ticket:
    magasin: str | None
    date_achat: date | None
    total: float | None
    articles: list[Article]


def disponible() -> bool:
    return bool(settings.ANTHROPIC_API_KEY)


def _nombre(valeur: object) -> float | None:
    if valeur in (None, ""):
        return None
    if isinstance(valeur, str):
        valeur = valeur.replace(",", ".").replace(" ", "")
    try:
        return float(valeur)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _date(valeur: object) -> date | None:
    if not isinstance(valeur, str):
        return None
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", valeur.strip())
    if not m:
        return None
    try:
        return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    except ValueError:
        return None


def _articles(donnees: list) -> list[Article]:
    """
    Filtre ce que le modèle renvoie.

    Un ticket mal lu doit donner moins de lignes, jamais des lignes fausses :
    l'utilisateur corrigera un oubli, il ne verra pas une erreur de saisie.
    """
    sortie: list[Article] = []
    for a in donnees:
        if not isinstance(a, dict):
            continue
        nom = str(a.get("nom") or "").strip()
        total = _nombre(a.get("prix_total"))
        if len(nom) < 2 or total is None or not (PRIX_MIN <= total <= PRIX_MAX):
            continue

        qte = _nombre(a.get("quantite")) or 1.0
        if not (0 < qte <= QUANTITE_MAX):
            qte = 1.0

        unitaire = _nombre(a.get("prix_unitaire"))
        # Un prix unitaire incohérent avec la ligne est recalculé plutôt que cru.
        if unitaire is None or abs(unitaire * qte - total) > max(0.5, total * 0.1):
            unitaire = round(total / qte, 2)

        sortie.append(Article(nom[:200], qte, round(unitaire, 2), round(total, 2)))
    return sortie


async def lire(image: bytes, mime_type: str) -> Ticket | None:
    """
    Lit le ticket. None si le modèle est indisponible ou la réponse inutilisable :
    l'appelant retombe alors sur Tesseract.
    """
    if not disponible():
        return None
    if mime_type not in ("image/jpeg", "image/png", "image/webp", "image/gif"):
        return None          # les PDF restent traités par l'ancien moteur

    client = anthropic.AsyncAnthropic(
        api_key=settings.ANTHROPIC_API_KEY, max_retries=1, timeout=40.0
    )
    try:
        reponse = await client.messages.create(
            model=MODELE,
            max_tokens=2048,
            system=CONSIGNE,
            messages=[{
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": mime_type,
                            "data": base64.b64encode(image).decode(),
                        },
                    },
                    {"type": "text", "text": "Extrais les achats de ce ticket."},
                ],
            }],
        )
    except Exception as e:
        log.warning("Lecture Vision indisponible : %s", type(e).__name__)
        return None

    brut = reponse.content[0].text.strip()
    brut = re.sub(r"^```(?:json)?|```$", "", brut, flags=re.MULTILINE).strip()
    try:
        d = json.loads(brut)
    except json.JSONDecodeError:
        log.warning("Réponse Vision illisible")
        return None
    if not isinstance(d, dict):
        return None

    articles = _articles(d.get("articles") or [])
    if not articles:
        return None

    total = _nombre(d.get("total"))
    somme = round(sum(a.prix_total for a in articles), 2)
    # Un total qui s'éloigne trop de la somme des lignes est écarté : mieux
    # vaut ne rien afficher que d'afficher un montant faux.
    if total is None or not (somme * 0.5 <= total <= somme * 2):
        total = somme

    magasin = (str(d.get("magasin")).strip()[:120] if d.get("magasin") else None)
    return Ticket(magasin, _date(d.get("date")), total, articles)
