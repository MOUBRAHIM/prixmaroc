"""
Réunir les produits en double et réparer leur historique de prix.

Le collecteur rapprochait un relevé d'un produit par égalité exacte du nom.
Comme le modèle réécrit ce nom à chaque passage — marque tantôt dans le nom,
tantôt dans son champ — un même article naissait plusieurs fois, et sa courbe
de prix se brisait en autant de morceaux.

    #305   Rondelles de poulet croustillantes LEZITA (1 kg)   2 relevés
    #1291  Rondelles de poulet croustillantes LEZITA          2 relevés
    #1342  Rondelles de poulet croustillantes                 2 relevés

Le collecteur ne crée plus ces doublons. Ce script répare l'existant : les
relevés, alertes et articles de liste des doublons rejoignent le produit
retenu, qui est le plus ancien — c'est lui qui porte le début de l'historique.

Les doublons ne sont pas supprimés mais désactivés : la fusion reste annulable
si elle se révèle fausse.

    python fusionner_doublons.py              # simulation, n'écrit rien
    python fusionner_doublons.py --appliquer  # applique
"""
from __future__ import annotations

import asyncio
import sys
from collections import defaultdict

from sqlalchemy import text as sql
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# psycopg en asynchrone n'accepte pas la boucle « proactor » de Windows.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from app.core.config import settings
from app.services.identite_produit import IndexProduits

engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def reperer(db: AsyncSession) -> dict[int, list[int]]:
    """Les doublons, groupés sous l'identifiant du produit à conserver."""
    lignes = (await db.execute(sql("""
        SELECT id, name, brand, unit_size
          FROM products
         WHERE is_active
         ORDER BY id
    """))).all()

    index = IndexProduits()
    groupes: dict[int, list[int]] = defaultdict(list)

    for produit_id, nom, marque, format_ in lignes:
        # Le premier rencontré est le plus ancien : c'est lui qu'on garde.
        retenu = index.trouver(nom, marque, format_)
        if retenu is None:
            index.ajouter(produit_id, nom, marque, format_)
        else:
            groupes[retenu].append(produit_id)

    return dict(groupes)


async def fusionner(db: AsyncSession, retenu: int, doublons: list[int]) -> dict[str, int]:
    """Rattache tout ce qui pend aux doublons, puis les met de côté."""
    bilan = {"prix": 0, "alertes": 0, "articles": 0, "prix_en_trop": 0}

    for doublon in doublons:
        # Un relevé du doublon qui ferait doublon de date avec le produit
        # retenu doit disparaître : deux prix le même jour dans le même
        # magasin créeraient une marche artificielle sur la courbe.
        en_trop = (await db.execute(sql("""
            DELETE FROM prices d
             USING prices g
             WHERE d.product_id = :doublon
               AND g.product_id = :retenu
               AND g.store_id = d.store_id
               AND g.recorded_at::date = d.recorded_at::date
            RETURNING d.id
        """), {"doublon": doublon, "retenu": retenu})).rowcount
        bilan["prix_en_trop"] += en_trop or 0

        for table, cle in (("prices", "prix"), ("price_alerts", "alertes"),
                           ("shopping_list_items", "articles")):
            deplaces = (await db.execute(sql(
                f"UPDATE {table} SET product_id = :retenu WHERE product_id = :doublon"
            ), {"retenu": retenu, "doublon": doublon})).rowcount
            bilan[cle] += deplaces or 0

        await db.execute(sql(
            "UPDATE products SET is_active = false, updated_at = now() WHERE id = :d"
        ), {"d": doublon})

    return bilan


async def main() -> None:
    appliquer = "--appliquer" in sys.argv

    async with Session() as db:
        groupes = await reperer(db)
        if not groupes:
            print("Aucun doublon : le catalogue est propre.")
            await engine.dispose()
            return

        noms = dict((await db.execute(sql(
            "SELECT id, name FROM products WHERE is_active"
        ))).all())

        total_doublons = sum(len(v) for v in groupes.values())
        print(f"{len(groupes)} produits recevront {total_doublons} doublons\n")

        cumul = {"prix": 0, "alertes": 0, "articles": 0, "prix_en_trop": 0}
        for retenu, doublons in sorted(groupes.items()):
            titre = (noms.get(retenu) or "?")[:54]
            print(f"  #{retenu} {titre}")
            for d in doublons:
                print(f"       <- #{d} {(noms.get(d) or '?')[:50]}")

            if appliquer:
                bilan = await fusionner(db, retenu, doublons)
                for k in cumul:
                    cumul[k] += bilan[k]

        if appliquer:
            await db.commit()
            print(f"\n[APPLIQUÉ] {cumul['prix']} relevés rattachés · "
                  f"{cumul['prix_en_trop']} relevés en double supprimés · "
                  f"{cumul['alertes']} alertes · {cumul['articles']} articles de liste")
            print(f"           {total_doublons} produits désactivés")
        else:
            print(f"\n[SIMULATION] rien n'a été écrit. "
                  f"Relancez avec --appliquer pour fusionner.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
