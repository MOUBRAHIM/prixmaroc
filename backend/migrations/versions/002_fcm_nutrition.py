"""FCM token + avatar_url dans User; colonnes nutrition dans Product

Revision ID: 002_fcm_nutrition
Revises: 001_dashboard_indexes
Create Date: 2026-04-05
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = "002_fcm_nutrition"
down_revision: Union[str, None] = "001_dashboard_indexes"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # User — token FCM + avatar + magasins préférés
    op.add_column("users", sa.Column("fcm_token", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("avatar_url", sa.String(500), nullable=True))
    op.add_column("users", sa.Column("preferred_stores", sa.Text(), nullable=True))  # JSON list of store slugs

    # Product — colonnes nutrition (per 100g)
    op.add_column("products", sa.Column("calories", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("proteins", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("lipids", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("carbs", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("fibers", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("nutriscore", sa.String(2), nullable=True))  # A/B/C/D/E


def downgrade() -> None:
    op.drop_column("products", "nutriscore")
    op.drop_column("products", "fibers")
    op.drop_column("products", "carbs")
    op.drop_column("products", "lipids")
    op.drop_column("products", "proteins")
    op.drop_column("products", "calories")
    op.drop_column("users", "preferred_stores")
    op.drop_column("users", "avatar_url")
    op.drop_column("users", "fcm_token")
