"""
reinit_admin.py — Définit un nouveau mot de passe pour un compte.

Le mot de passe est saisi au clavier, masqué, et n'apparaît ni à l'écran, ni
dans l'historique du terminal, ni dans aucun fichier. Il est haché avec la
même fonction que l'application avant d'être enregistré.

Usage :
    python reinit_admin.py                      # compte admin@prixmaroc.ma
    python reinit_admin.py autre@exemple.ma     # un autre compte
"""
from __future__ import annotations

import asyncio
import getpass
import sys

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings
from app.models import User
from app.utils.security import hash_password, verify_password

LONGUEUR_MIN = 10


def demander_mot_de_passe() -> str:
    while True:
        mdp = getpass.getpass("Nouveau mot de passe : ")
        if len(mdp) < LONGUEUR_MIN:
            print(f"  Trop court — au moins {LONGUEUR_MIN} caractères.")
            continue
        if getpass.getpass("Confirmez            : ") != mdp:
            print("  Les deux saisies diffèrent, recommencez.")
            continue
        return mdp


async def main() -> None:
    email = sys.argv[1] if len(sys.argv) > 1 else "admin@prixmaroc.ma"

    engine = create_async_engine(settings.DATABASE_URL, echo=False, pool_pre_ping=True)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with Session() as db:
        compte = (await db.execute(select(User).where(User.email == email))).scalar_one_or_none()
        if compte is None:
            print(f"Aucun compte {email}.")
            await engine.dispose()
            sys.exit(1)

        role = "administrateur" if compte.is_superuser else "utilisateur"
        print(f"Compte : {email} (identifiant « {compte.username} », {role})\n")

        mdp = demander_mot_de_passe()
        compte.password_hash = hash_password(mdp)
        await db.commit()

        # On relit la ligne et on vérifie : un enregistrement qui ne permettrait
        # pas de se connecter serait pire que l'ancien mot de passe oublié.
        await db.refresh(compte)
        ok = verify_password(mdp, compte.password_hash)

    await engine.dispose()
    print("\nMot de passe enregistré et vérifié." if ok
          else "\n[ÉCHEC] Le mot de passe enregistré ne se vérifie pas.")


if __name__ == "__main__":
    asyncio.run(main())
