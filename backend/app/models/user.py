from datetime import datetime
from sqlalchemy import String, Boolean, DateTime, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(20))
    city: Mapped[str | None] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False)
    fcm_token: Mapped[str | None] = mapped_column(String(500))
    avatar_url: Mapped[str | None] = mapped_column(String(500))
    preferred_stores: Mapped[str | None] = mapped_column(Text)  # JSON: ["marjane","carrefour"]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    shopping_lists: Mapped[list["ShoppingList"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    price_alerts: Mapped[list["PriceAlert"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    ocr_scans: Mapped[list["OcrScan"]] = relationship(back_populates="user", cascade="all, delete-orphan")
    souk_prices: Mapped[list["SoukPrice"]] = relationship(back_populates="user", cascade="all, delete-orphan")
