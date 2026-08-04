from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_

from app.models import User
from app.schemas import UserCreate, Token
from app.utils.security import hash_password, verify_password, create_access_token


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, payload: UserCreate) -> User:
        # Check duplicate email
        result = await self.db.execute(select(User).where(User.email == payload.email))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email déjà utilisé")

        result = await self.db.execute(select(User).where(User.username == payload.username))
        if result.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Nom d'utilisateur déjà pris")

        user = User(
            email=payload.email,
            username=payload.username,
            full_name=payload.full_name,
            phone=payload.phone,
            city=payload.city,
            password_hash=hash_password(payload.password),
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    async def login(self, username_or_email: str, password: str) -> Token:
        # Accepte email OU nom d'utilisateur
        result = await self.db.execute(
            select(User).where(
                or_(
                    User.email == username_or_email,
                    User.username == username_or_email,
                )
            )
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou mot de passe incorrect",
                headers={"WWW-Authenticate": "Bearer"},
            )
        if not user.is_active:
            raise HTTPException(status_code=400, detail="Compte désactivé")

        token = create_access_token(subject=user.id)
        return Token(access_token=token)
