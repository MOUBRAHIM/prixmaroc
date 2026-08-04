from datetime import datetime, date
from sqlalchemy import String, Integer, ForeignKey, DateTime, Date, Numeric, Boolean, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from .base import Base


class PriceSource(str, enum.Enum):
    SCRAPER = "scraper"
    OCR = "ocr"
    MANUAL = "manual"
    AI = "ai"


class Price(Base):
    __tablename__ = "prices"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), nullable=False, index=True)
    store_id: Mapped[int] = mapped_column(Integer, ForeignKey("stores.id"), nullable=False, index=True)
    price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), default="MAD")
    is_promo: Mapped[bool] = mapped_column(Boolean, default=False)
    promo_price: Mapped[float | None] = mapped_column(Numeric(10, 2))
    promo_start: Mapped[date | None] = mapped_column(Date)
    promo_end: Mapped[date | None] = mapped_column(Date)
    source: Mapped[PriceSource] = mapped_column(
        Enum(PriceSource, values_callable=lambda x: [e.value for e in x]),
        default=PriceSource.MANUAL
    )
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True)

    # Relationships
    product: Mapped["Product"] = relationship(back_populates="prices")
    store: Mapped["Store"] = relationship(back_populates="prices")
