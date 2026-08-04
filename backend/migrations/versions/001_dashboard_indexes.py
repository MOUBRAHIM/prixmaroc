"""Indexes pour les requêtes agrégées du dashboard

Revision ID: 001_dashboard_indexes
Revises:
Create Date: 2026-03-29

Ajoute les index composites nécessaires pour les requêtes agrégées du dashboard :
  - ocr_scans(user_id, status, created_at) : filtrage rapide par utilisateur + période
  - prices(product_id, recorded_at)         : sous-requêtes latest-price-per-store
  - prices(store_id, is_promo, recorded_at) : requêtes promotions actives
  - price_alerts(user_id, is_active)        : comptage alertes actives
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "001_dashboard_indexes"
down_revision: Union[str, None] = "000_create_all_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Index composite pour requêtes OcrScan du dashboard
    op.create_index(
        "ix_ocr_scans_user_status_created",
        "ocr_scans",
        ["user_id", "status", "created_at"],
        unique=False,
    )

    # Index composite pour le calcul d'historique de prix (latest per store)
    op.create_index(
        "ix_prices_product_recorded",
        "prices",
        ["product_id", "recorded_at"],
        unique=False,
    )

    # Index pour les requêtes de promotions actives
    op.create_index(
        "ix_prices_store_promo_recorded",
        "prices",
        ["store_id", "is_promo", "recorded_at"],
        unique=False,
    )

    # Index pour le comptage d'alertes actives par utilisateur
    op.create_index(
        "ix_price_alerts_user_active",
        "price_alerts",
        ["user_id", "is_active"],
        unique=False,
    )

    # Index sur Store.city pour les requêtes filtrées par ville
    op.create_index(
        "ix_stores_city_active",
        "stores",
        ["city", "is_active"],
        unique=False,
    )

    # Index sur Product.brand pour filtrage par marque
    op.create_index(
        "ix_products_brand_active",
        "products",
        ["brand", "is_active"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_products_brand_active", table_name="products")
    op.drop_index("ix_stores_city_active", table_name="stores")
    op.drop_index("ix_price_alerts_user_active", table_name="price_alerts")
    op.drop_index("ix_prices_store_promo_recorded", table_name="prices")
    op.drop_index("ix_prices_product_recorded", table_name="prices")
    op.drop_index("ix_ocr_scans_user_status_created", table_name="ocr_scans")
