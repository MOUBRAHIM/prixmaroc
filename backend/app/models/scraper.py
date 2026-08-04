from datetime import datetime
from sqlalchemy import (
    String, Integer, ForeignKey, DateTime, Boolean,
    func, Text, JSON, Enum, Float,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum
from .base import Base


class ScraperStatus(str, enum.Enum):
    IDLE      = "idle"
    RUNNING   = "running"
    SUCCESS   = "success"
    FAILED    = "failed"
    CAPTCHA   = "captcha"
    PAUSED    = "paused"


class ScraperConfig(Base):
    """Configuration d'un scraper pour un site cible."""
    __tablename__ = "scraper_configs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)

    # Sélecteurs CSS configurables (pour le scraper générique)
    selectors: Mapped[dict | None] = mapped_column(JSON)
    # Ex: {"product": ".product-item", "name": ".product-name",
    #      "price": ".price", "image": "img.product-img",
    #      "category": ".breadcrumb li:last-child", "next_page": "a.next"}

    # URLs des pages catalogue à scraper
    catalog_urls: Mapped[list | None] = mapped_column(JSON)

    # Rate limiting
    rate_limit_seconds: Mapped[float] = mapped_column(Float, default=2.0)
    max_retries: Mapped[int] = mapped_column(Integer, default=3)

    # Schedule (cron expression)
    schedule_cron: Mapped[str] = mapped_column(String(50), default="0 3 * * *")  # 3h du matin

    # État
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_status: Mapped[ScraperStatus] = mapped_column(
        Enum(ScraperStatus, values_callable=lambda x: [e.value for e in x]),
        default=ScraperStatus.IDLE
    )

    # Cloudflare R2
    store_images: Mapped[bool] = mapped_column(Boolean, default=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    runs: Mapped[list["ScraperRun"]] = relationship(back_populates="config", cascade="all, delete-orphan")


class ScraperRun(Base):
    """Historique d'exécution d'un scraper."""
    __tablename__ = "scraper_runs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    config_id: Mapped[int] = mapped_column(Integer, ForeignKey("scraper_configs.id"), nullable=False, index=True)

    status: Mapped[ScraperStatus] = mapped_column(
        Enum(ScraperStatus, values_callable=lambda x: [e.value for e in x]),
        default=ScraperStatus.RUNNING
    )
    triggered_by: Mapped[str] = mapped_column(String(50), default="scheduler")  # "scheduler" | "admin" | "api"

    products_found: Mapped[int] = mapped_column(Integer, default=0)
    products_new: Mapped[int] = mapped_column(Integer, default=0)
    products_updated: Mapped[int] = mapped_column(Integer, default=0)
    products_duplicate: Mapped[int] = mapped_column(Integer, default=0)
    images_uploaded: Mapped[int] = mapped_column(Integer, default=0)
    pages_scraped: Mapped[int] = mapped_column(Integer, default=0)
    captcha_hits: Mapped[int] = mapped_column(Integer, default=0)

    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float | None] = mapped_column(Float)

    # Relationships
    config: Mapped["ScraperConfig"] = relationship(back_populates="runs")
    logs: Mapped[list["ScraperLog"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class ScraperLog(Base):
    """Logs détaillés ligne par ligne d'un run."""
    __tablename__ = "scraper_logs"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("scraper_runs.id"), nullable=False, index=True)

    level: Mapped[str] = mapped_column(String(10), default="INFO")  # INFO | WARN | ERROR
    message: Mapped[str] = mapped_column(Text, nullable=False)
    url: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    run: Mapped["ScraperRun"] = relationship(back_populates="logs")
