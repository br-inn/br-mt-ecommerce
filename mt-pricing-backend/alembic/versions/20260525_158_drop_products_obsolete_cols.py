"""drop_products_obsolete_cols

Revision ID: 20260525_158
Revises: 640950af09ba
Create Date: 2026-05-25 18:00:00.000000+00:00

"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260525_158"
down_revision = "640950af09ba"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("SET LOCAL statement_timeout = 0")
    for col in ("iso5211_interface", "kv", "dn_real", "kv2", "manufacturing_method", "actuator", "torque_nm"):
        op.execute(f"ALTER TABLE products DROP COLUMN IF EXISTS {col}")


def downgrade() -> None:
    op.add_column(
        "products",
        sa.Column("torque_nm", sa.NUMERIC(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("actuator", sa.TEXT(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("manufacturing_method", sa.TEXT(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("kv2", sa.NUMERIC(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("dn_real", sa.TEXT(), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("kv", sa.NUMERIC(precision=10, scale=2), nullable=True),
    )
    op.add_column(
        "products",
        sa.Column("iso5211_interface", sa.TEXT(), nullable=True),
    )
