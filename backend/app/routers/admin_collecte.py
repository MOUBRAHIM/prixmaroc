"""
Router /admin/collecte — déclencher la mise à jour des prix.

Le panneau d'administration proposait un bouton par enseigne, hérité d'une
infrastructure de scraping jamais mise en service : la table des
configurations est vide, et ces boutons répondaient 404. Les sites visés
n'existent d'ailleurs plus sous cette forme.

La collecte qui fonctionne lit les catalogues publiés en ligne et en extrait
les produits. C'est elle que la tâche hebdomadaire exécute ; ce routeur
l'expose pour un déclenchement manuel, sans dupliquer le code.

La collecte prend plusieurs minutes : elle part en tâche de fond et la
réponse est immédiate. L'état se consulte ensuite.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.utils.deps import get_superuser

log = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/collecte", tags=["admin — collecte"])

# Une seule collecte à la fois : deux exécutions simultanées écriraient les
# mêmes relevés et doubleraient la dépense.
_en_cours: dict[str, Any] = {"actif": False, "depuis": None, "bilan": None, "erreur": None}


async def _executer(limite: int) -> None:
    from collecte_prix import CollecteInterrompue, collecter

    _en_cours.update(actif=True, depuis=datetime.now(timezone.utc), bilan=None, erreur=None)
    try:
        bilan = await collecter(appliquer=True, limite=limite, journal=lambda *_: None)
        _en_cours["bilan"] = bilan
        log.info("[collecte] %s prix ajoutés", bilan.get("prix"))
    except CollecteInterrompue as arret:
        _en_cours["erreur"] = str(arret)
        log.warning("[collecte] interrompue : %s", arret)
    except Exception as e:                                   # noqa: BLE001
        _en_cours["erreur"] = f"{type(e).__name__}"
        log.exception("[collecte] échec")
    finally:
        _en_cours["actif"] = False


@router.post("", summary="Lancer une collecte des prix")
async def lancer(
    catalogues: int = Query(12, ge=1, le=30, description="Nombre de catalogues à lire"),
    _=Depends(get_superuser),
):
    if _en_cours["actif"]:
        raise HTTPException(
            status_code=409,
            detail="Une collecte est déjà en cours. Patientez avant d'en lancer une autre.",
        )
    # On ne passe pas par BackgroundTasks : la réponse doit partir tout de
    # suite, sans attendre la fin d'une tâche de plusieurs minutes.
    asyncio.create_task(_executer(catalogues))
    return {
        "statut": "lancee",
        "catalogues": catalogues,
        "message": f"Collecte lancée sur {catalogues} catalogues. "
                   "Comptez deux à cinq minutes.",
    }


@router.get("", summary="État de la collecte et fraîcheur des prix")
async def etat(db: AsyncSession = Depends(get_db), _=Depends(get_superuser)):
    ligne = (await db.execute(sql("""
        SELECT MAX(recorded_at)                                        AS dernier,
               COUNT(*) FILTER (WHERE recorded_at > now() - interval '24 hours') AS jour,
               COUNT(*) FILTER (WHERE recorded_at > now() - interval '7 days')   AS semaine,
               COUNT(*)                                                AS total
          FROM prices
    """))).one()

    return {
        "en_cours": _en_cours["actif"],
        "depuis": _en_cours["depuis"].isoformat() if _en_cours["depuis"] else None,
        "dernier_bilan": _en_cours["bilan"],
        "derniere_erreur": _en_cours["erreur"],
        "dernier_releve": ligne.dernier.isoformat() if ligne.dernier else None,
        "prix_24h": ligne.jour,
        "prix_7j": ligne.semaine,
        "prix_total": ligne.total,
    }
