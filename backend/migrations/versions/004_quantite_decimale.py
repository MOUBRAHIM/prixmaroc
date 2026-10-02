"""Quantité décimale sur les articles de liste

Un article de liste se comptait en entiers. Le générateur raisonne pourtant
en poids pour ce qui se vend au poids : « 1,5 kg de viande » est une quantité
normale, que le souk vend au demi-kilo. L'enregistrement de ces listes
échouait donc avec « Input should be a valid integer, got a number with a
fractional part », et l'utilisateur perdait sa liste entière.

Arrondir aurait été plus simple, mais faux : 1,5 kg de viande deviendrait
2 kg, soit un tiers de dépense en plus sur le poste le plus cher du panier.

Revision ID: 004_quantite_decimale
Revises: 003_souk_prices
Create Date: 2026-10-02
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004_quantite_decimale"
down_revision: Union[str, None] = "003_souk_prices"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "shopping_list_items",
        "quantity",
        existing_type=sa.Integer(),
        type_=sa.Numeric(8, 2),
        existing_nullable=True,
        postgresql_using="quantity::numeric(8,2)",
    )


def downgrade() -> None:
    # Les décimales sont perdues : c'est le sens même du retour en arrière.
    op.alter_column(
        "shopping_list_items",
        "quantity",
        existing_type=sa.Numeric(8, 2),
        type_=sa.Integer(),
        existing_nullable=True,
        postgresql_using="round(quantity)::integer",
    )
