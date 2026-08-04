@echo off
chcp 65001 >nul
title PrixMaroc — Comptes utilisateurs

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║           PRIXMAROC — Gestion des comptes                ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

cd /d "C:\Users\HP 840 G7\Desktop\PrixMaroc"

echo [1/2] Lecture des comptes existants...
echo.
docker exec prixmaroc-backend-1 python -c "
import asyncio, sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.user import User
import os

async def main():
    engine = create_async_engine(os.environ['DATABASE_URL'], echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        r = await db.execute(sa.select(User.id, User.email, User.username, User.is_superuser))
        users = r.fetchall()
        print('ID  ROLE       EMAIL                          USERNAME')
        print('-' * 70)
        for u in users:
            role = 'ADMIN' if u[3] else 'user '
            print(f'{u[0]:<3} [{role}]   {u[1]:<35} {u[2] or \"-\"}')
    await engine.dispose()

asyncio.run(main())
"

echo.
echo ════════════════════════════════════════════════════════════
echo.
echo [2/2] Reinitialiser le mot de passe d'un compte admin...
echo.
set /p EMAIL="Entrez l'email du compte admin (ou appuyez ENTREE pour creer admin@prixmaroc.ma) : "

if "%EMAIL%"=="" set EMAIL=admin@prixmaroc.ma

set /p NEWPASS="Nouveau mot de passe (min 8 caracteres) : "

docker exec prixmaroc-backend-1 python -c "
import asyncio, sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from app.models.user import User
from app.utils.security import hash_password
import os

EMAIL = '%EMAIL%'
PASSWORD = '%NEWPASS%'

async def main():
    engine = create_async_engine(os.environ['DATABASE_URL'], echo=False)
    Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with Session() as db:
        r = await db.execute(sa.select(User).where(User.email == EMAIL))
        user = r.scalar_one_or_none()
        if user:
            user.password_hash = hash_password(PASSWORD)
            user.is_superuser = True
            user.is_active = True
            await db.commit()
            print(f'OK  Mot de passe mis a jour pour {EMAIL}')
            print(f'    Role admin : OUI')
        else:
            new_user = User(
                email=EMAIL,
                username='admin',
                password_hash=hash_password(PASSWORD),
                is_superuser=True,
                is_active=True,
            )
            db.add(new_user)
            await db.commit()
            print(f'OK  Compte admin cree : {EMAIL}')
    await engine.dispose()

asyncio.run(main())
"

echo.
echo ════════════════════════════════════════════════════════════
echo  Identifiants :
echo    Email    : %EMAIL%
echo    Password : %NEWPASS%
echo    Panel admin : http://localhost:5173
echo ════════════════════════════════════════════════════════════
echo.
pause
