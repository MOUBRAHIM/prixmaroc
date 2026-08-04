from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, Boolean, Numeric, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base


class PriceAlert(Base):
    __tablename__ = "price_alerts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    store_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stores.id"), nullable=True)
    target_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    triggered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user: Mapped["User"] = relationship(back_populates="price_alerts")
    product: Mapped["Product"] = relationship(back_populates="price_alerts")
    store: Mapped["Store | None"] = relationship()
