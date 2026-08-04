"""
Prix communautaires du souk — contributions citoyennes.

Contrairement aux produits de grande surface (scrapés / OCR), ces prix
concernent les produits frais des souks marocains : légumes, fruits, viande
halal, poisson. Ils sont proposés par les utilisateurs, modérés (anti-fraude /
anti-aberration) puis agrégés en prix médian par ville.
"""
from __future__ import annotations

import enum
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Enum, Float, ForeignKey, Integer, Numeric, String,
    Text, UniqueConstraint, func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class SoukCategory(str, enum.Enum):
    LEGUMES = "legumes"      # 🥦 Légumes & herbes
    FRUITS = "fruits"        # 🍊 Fruits frais
    VIANDE = "viande"        # 🥩 Viande rouge & volaille (halal)
    POISSON = "poisson"      # 🐟 Poissons & fruits de mer


class SoukStatus(str, enum.Enum):
    APPROVED = "approved"    # visible publiquement
    PENDING = "pending"      # en attente de vérification (prix douteux)
    REJECTED = "rejected"    # rejeté (aberrant / fraude)


class SoukPrice(Base):
    """Un relevé de prix d'un produit de souk proposé par un citoyen."""
    __tablename__ = "souk_prices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    item_name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    category: Mapped[SoukCategory] = mapped_column(
        Enum(SoukCategory, values_callable=lambda x: [e.value for e in x]),
        nullable=False, index=True,
    )
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="kg")  # kg, botte, pièce, caisse
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MAD")

    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    neighborhood: Mapped[str | None] = mapped_column(String(120))   # quartier / nom du souk
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    photo_url: Mapped[str | None] = mapped_column(String(500))
    note: Mapped[str | None] = mapped_column(Text)

    # Modération
    status: Mapped[SoukStatus] = mapped_column(
        Enum(SoukStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False, default=SoukStatus.PENDING, index=True,
    )
    moderation_reason: Mapped[str | None] = mapped_column(String(300))
    moderation_source: Mapped[str | None] = mapped_column(String(20))  # auto | claude | manual

    # Votes communautaires (dénormalisés pour le tri rapide)
    upvotes: Mapped[int] = mapped_column(Integer, default=0)
    downvotes: Mapped[int] = mapped_column(Integer, default=0)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="souk_prices")
    votes: Mapped[list["SoukVote"]] = relationship(
        back_populates="souk_price", cascade="all, delete-orphan",
    )


class SoukVote(Base):
    """Vote 👍/👎 d'un utilisateur sur un relevé de prix (un seul par user)."""
    __tablename__ = "souk_votes"
    __table_args__ = (
        UniqueConstraint("souk_price_id", "user_id", name="uq_souk_vote_user"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    souk_price_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("souk_prices.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    value: Mapped[int] = mapped_column(Integer, nullable=False)  # +1 ou -1
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    souk_price: Mapped["SoukPrice"] = relationship(back_populates="votes")
