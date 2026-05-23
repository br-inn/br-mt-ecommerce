"""Add hs_code and country_of_origin to products.

Revision ID: 20260518137a
Revises: 20260517_143
Create Date: 2026-05-18
"""

from __future__ import annotations
from alembic import op
import sqlalchemy as sa

revision = "20260518137a"
down_revision = "20260517_143"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("hs_code", sa.Text(), nullable=True))
    op.add_column("products", sa.Column("country_of_origin", sa.Text(), nullable=True))
    op.create_index("idx_products_hs_code", "products", ["hs_code"])


def downgrade() -> None:
    op.drop_index("idx_products_hs_code", "products")
    op.drop_column("products", "country_of_origin")
    op.drop_column("products", "hs_code")
