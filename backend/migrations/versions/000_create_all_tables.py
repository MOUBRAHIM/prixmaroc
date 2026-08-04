"""Création initiale de toutes les tables PrixMaroc

Revision ID: 000_create_all_tables
Revises:
Create Date: 2026-03-29

Crée le schéma complet :
  categories, users, stores, products, prices,
  shopping_lists, shopping_list_items, price_alerts,
  ocr_scans, scraper_configs, scraper_runs, scraper_logs
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "000_create_all_tables"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── categories ────────────────────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("icon", sa.String(100), nullable=True),
        sa.Column("parent_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["parent_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_categories_id", "categories", ["id"])
    op.create_index("ix_categories_slug", "categories", ["slug"], unique=True)

    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("username", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_index("ix_users_username", "users", ["username"], unique=True)

    # ── stores ────────────────────────────────────────────────────────────────
    op.create_table(
        "stores",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("phone", sa.String(20), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("logo_url", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("scraping_enabled", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("scraping_url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stores_id", "stores", ["id"])
    op.create_index("ix_stores_name", "stores", ["name"])
    op.create_index("ix_stores_slug", "stores", ["slug"], unique=True)
    op.create_index("ix_stores_city", "stores", ["city"])

    # ── products ──────────────────────────────────────────────────────────────
    op.create_table(
        "products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(500), nullable=False),
        sa.Column("slug", sa.String(500), nullable=False),
        sa.Column("barcode", sa.String(100), nullable=True),
        sa.Column("brand", sa.String(255), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("unit_size", sa.String(50), nullable=True),
        sa.Column("category_id", sa.Integer(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["category_id"], ["categories.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_products_id", "products", ["id"])
    op.create_index("ix_products_name", "products", ["name"])
    op.create_index("ix_products_slug", "products", ["slug"], unique=True)
    op.create_index("ix_products_barcode", "products", ["barcode"], unique=True)
    op.create_index("ix_products_brand", "products", ["brand"])

    # ── prices ────────────────────────────────────────────────────────────────
    op.create_table(
        "prices",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False, server_default="MAD"),
        sa.Column("is_promo", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("promo_price", sa.Numeric(10, 2), nullable=True),
        sa.Column("promo_start", sa.Date(), nullable=True),
        sa.Column("promo_end", sa.Date(), nullable=True),
        sa.Column(
            "source",
            sa.Enum("scraper", "ocr", "manual", "ai", name="pricesource"),
            nullable=False,
            server_default="manual",
        ),
        sa.Column("recorded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_prices_id", "prices", ["id"])
    op.create_index("ix_prices_product_id", "prices", ["product_id"])
    op.create_index("ix_prices_store_id", "prices", ["store_id"])
    op.create_index("ix_prices_recorded_at", "prices", ["recorded_at"])

    # ── shopping_lists ────────────────────────────────────────────────────────
    op.create_table(
        "shopping_lists",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_shared", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("share_token", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopping_lists_id", "shopping_lists", ["id"])
    op.create_index("ix_shopping_lists_user_id", "shopping_lists", ["user_id"])
    op.create_index("ix_shopping_lists_share_token", "shopping_lists", ["share_token"], unique=True)

    # ── shopping_list_items ───────────────────────────────────────────────────
    op.create_table(
        "shopping_list_items",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("list_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=True),
        sa.Column("custom_name", sa.String(255), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("unit", sa.String(50), nullable=True),
        sa.Column("is_checked", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("note", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["list_id"], ["shopping_lists.id"]),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_shopping_list_items_id", "shopping_list_items", ["id"])
    op.create_index("ix_shopping_list_items_list_id", "shopping_list_items", ["list_id"])

    # ── price_alerts ──────────────────────────────────────────────────────────
    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=True),
        sa.Column("target_price", sa.Numeric(10, 2), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"]),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_price_alerts_id", "price_alerts", ["id"])
    op.create_index("ix_price_alerts_user_id", "price_alerts", ["user_id"])
    op.create_index("ix_price_alerts_product_id", "price_alerts", ["product_id"])

    # ── ocr_scans ─────────────────────────────────────────────────────────────
    op.create_table(
        "ocr_scans",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("parsed_data", sa.JSON(), nullable=True),
        sa.Column(
            "status",
            sa.Enum("pending", "processing", "done", "failed", name="scanstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["store_id"], ["stores.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ocr_scans_id", "ocr_scans", ["id"])
    op.create_index("ix_ocr_scans_user_id", "ocr_scans", ["user_id"])

    # ── scraper_configs ───────────────────────────────────────────────────────
    op.create_table(
        "scraper_configs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("site_slug", sa.String(100), nullable=False),
        sa.Column("site_name", sa.String(255), nullable=False),
        sa.Column("base_url", sa.String(500), nullable=False),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("schedule_cron", sa.String(100), nullable=True),
        sa.Column("selectors", sa.JSON(), nullable=True),
        sa.Column("headers", sa.JSON(), nullable=True),
        sa.Column("rate_limit_seconds", sa.Float(), nullable=False, server_default="2.0"),
        sa.Column("max_pages", sa.Integer(), nullable=False, server_default="50"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scraper_configs_id", "scraper_configs", ["id"])
    op.create_index("ix_scraper_configs_site_slug", "scraper_configs", ["site_slug"], unique=True)

    # ── scraper_runs ──────────────────────────────────────────────────────────
    op.create_table(
        "scraper_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("config_id", sa.Integer(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum("running", "success", "failed", "partial", name="runstatus"),
            nullable=False,
            server_default="running",
        ),
        sa.Column("pages_scraped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_found", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_new", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("products_updated", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("duplicates_skipped", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["config_id"], ["scraper_configs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scraper_runs_id", "scraper_runs", ["id"])
    op.create_index("ix_scraper_runs_config_id", "scraper_runs", ["config_id"])

    # ── scraper_logs ──────────────────────────────────────────────────────────
    op.create_table(
        "scraper_logs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("run_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.String(20), nullable=False, server_default="INFO"),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("url", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["run_id"], ["scraper_runs.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_scraper_logs_id", "scraper_logs", ["id"])
    op.create_index("ix_scraper_logs_run_id", "scraper_logs", ["run_id"])


def downgrade() -> None:
    op.drop_table("scraper_logs")
    op.drop_table("scraper_runs")
    op.drop_table("scraper_configs")
    op.drop_table("ocr_scans")
    op.drop_table("price_alerts")
    op.drop_table("shopping_list_items")
    op.drop_table("shopping_lists")
    op.drop_table("prices")
    op.drop_table("products")
    op.drop_table("stores")
    op.drop_table("users")
    op.drop_table("categories")
    op.execute("DROP TYPE IF EXISTS pricesource")
    op.execute("DROP TYPE IF EXISTS scanstatus")
    op.execute("DROP TYPE IF EXISTS runstatus")
