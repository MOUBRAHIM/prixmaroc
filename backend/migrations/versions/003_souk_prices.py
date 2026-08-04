"""Prix communautaires du souk (souk_prices + souk_votes)

Revision ID: 003_souk_prices
Revises: 002_fcm_nutrition
Create Date: 2026-07-31
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "003_souk_prices"
down_revision: Union[str, None] = "002_fcm_nutrition"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False : les types sont créés explicitement ci-dessous (une seule fois),
# les colonnes ne doivent donc PAS tenter de les recréer.
souk_category = postgresql.ENUM(
    "legumes", "fruits", "viande", "poisson", name="soukcategory", create_type=False,
)
souk_status = postgresql.ENUM(
    "approved", "pending", "rejected", name="soukstatus", create_type=False,
)


def upgrade() -> None:
    bind = op.get_bind()
    postgresql.ENUM("legumes", "fruits", "viande", "poisson", name="soukcategory").create(bind, checkfirst=True)
    postgresql.ENUM("approved", "pending", "rejected", name="soukstatus").create(bind, checkfirst=True)

    op.create_table(
        "souk_prices",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("item_name", sa.String(120), nullable=False),
        sa.Column("category", souk_category, nullable=False),
        sa.Column("unit", sa.String(20), nullable=False, server_default="kg"),
        sa.Column("price", sa.Numeric(10, 2), nullable=False),
        sa.Column("currency", sa.String(3), server_default="MAD"),
        sa.Column("city", sa.String(100), nullable=False),
        sa.Column("neighborhood", sa.String(120), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("photo_url", sa.String(500), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("status", souk_status, nullable=False, server_default="pending"),
        sa.Column("moderation_reason", sa.String(300), nullable=True),
        sa.Column("moderation_source", sa.String(20), nullable=True),
        sa.Column("upvotes", sa.Integer(), server_default="0"),
        sa.Column("downvotes", sa.Integer(), server_default="0"),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_souk_prices_item_name", "souk_prices", ["item_name"])
    op.create_index("ix_souk_prices_category", "souk_prices", ["category"])
    op.create_index("ix_souk_prices_city", "souk_prices", ["city"])
    op.create_index("ix_souk_prices_status", "souk_prices", ["status"])
    op.create_index("ix_souk_prices_user_id", "souk_prices", ["user_id"])
    op.create_index("ix_souk_prices_created_at", "souk_prices", ["created_at"])

    op.create_table(
        "souk_votes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("souk_price_id", sa.Integer(),
                  sa.ForeignKey("souk_prices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("value", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("souk_price_id", "user_id", name="uq_souk_vote_user"),
    )
    op.create_index("ix_souk_votes_souk_price_id", "souk_votes", ["souk_price_id"])
    op.create_index("ix_souk_votes_user_id", "souk_votes", ["user_id"])


def downgrade() -> None:
    op.drop_table("souk_votes")
    op.drop_table("souk_prices")
    souk_status.drop(op.get_bind(), checkfirst=True)
    souk_category.drop(op.get_bind(), checkfirst=True)
