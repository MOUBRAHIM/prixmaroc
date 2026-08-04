from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, Boolean, func, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class ShoppingList(Base):
    __tablename__ = "shopping_lists"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    is_shared: Mapped[bool] = mapped_column(Boolean, default=False)
    share_token: Mapped[str | None] = mapped_column(String(64), unique=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    user: Mapped["User"] = relationship(back_populates="shopping_lists")
    items: Mapped[list["ShoppingListItem"]] = relationship(back_populates="list", cascade="all, delete-orphan")


class ShoppingListItem(Base):
    __tablename__ = "shopping_list_items"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    list_id: Mapped[int] = mapped_column(Integer, ForeignKey("shopping_lists.id"), nullable=False, index=True)
    product_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("products.id"), nullable=True)
    custom_name: Mapped[str | None] = mapped_column(String(255))  # when product not in DB
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    unit: Mapped[str | None] = mapped_column(String(50))
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(Text)

    # Relationships
    list: Mapped["ShoppingList"] = relationship(back_populates="items")
    product: Mapped["Product | None"] = relationship(back_populates="list_items")
