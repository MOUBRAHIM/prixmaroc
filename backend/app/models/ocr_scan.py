from datetime import datetime
from sqlalchemy import String, Integer, ForeignKey, DateTime, func, Text, JSON, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from .base import Base


class ScanStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


class OcrScan(Base):
    __tablename__ = "ocr_scans"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    store_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("stores.id"), nullable=True)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_text: Mapped[str | None] = mapped_column(Text)
    parsed_data: Mapped[dict | None] = mapped_column(JSON)  # structured products/prices extracted
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, values_callable=lambda x: [e.value for e in x]),
        default=ScanStatus.PENDING
    )
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # Relationships
    user: Mapped["User"] = relationship(back_populates="ocr_scans")
    store: Mapped["Store | None"] = relationship()
