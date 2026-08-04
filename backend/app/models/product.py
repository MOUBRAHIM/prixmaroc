from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, func, Text, Boolean, Float
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    slug: Mapped[str] = mapped_column(String(500), unique=True, nullable=False, index=True)
    barcode: Mapped[str | None] = mapped_column(String(100), unique=True, index=True)
    brand: Mapped[str | None] = mapped_column(String(255), index=True)
    description: Mapped[str | None] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(500))
    unit: Mapped[str | None] = mapped_column(String(50))  # kg, L, piece, pack...
    unit_size: Mapped[str | None] = mapped_column(String(50))  # 1kg, 500g, 1L...
    category_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("categories.id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Nutrition (per 100g)
    calories: Mapped[float | None] = mapped_column(Float)
    proteins: Mapped[float | None] = mapped_column(Float)
    lipids: Mapped[float | None] = mapped_column(Float)
    carbs: Mapped[float | None] = mapped_column(Float)
    fibers: Mapped[float | None] = mapped_column(Float)
    nutriscore: Mapped[str | None] = mapped_column(String(2))  # A/B/C/D/E
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    category: Mapped["Category | None"] = relationship(back_populates="products")
    prices: Mapped[list["Price"]] = relationship(back_populates="product", cascade="all, delete-orphan")
    list_items: Mapped[list["ShoppingListItem"]] = relationship(back_populates="product")
    price_alerts: Mapped[list["PriceAlert"]] = relationship(back_populates="product", cascade="all, delete-orphan")
