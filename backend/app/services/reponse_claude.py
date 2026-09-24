"""
reponse_claude.py — Extraction du texte d'une réponse Claude.

Une réponse ne contient pas toujours un seul bloc de texte : selon le modèle,
elle peut commencer par un bloc de réflexion. Lire `content[0].text` lève
alors une AttributeError, et l'appel entier bascule en mode dégradé sans
qu'on comprenne pourquoi — c'est exactement ce qui faisait échouer la
génération de liste avec Sonnet 5.

On parcourt donc les blocs et on assemble ceux qui portent du texte.
"""
from __future__ import annotations


def texte_de(reponse) -> str:
    """Texte de la réponse, blocs de réflexion ignorés."""
    morceaux: list[str] = []
    for bloc in getattr(reponse, "content", None) or []:
        if getattr(bloc, "type", None) == "text" or hasattr(bloc, "text"):
            valeur = getattr(bloc, "text", None)
            if isinstance(valeur, str):
                morceaux.append(valeur)
    return "\n".join(morceaux).strip()
