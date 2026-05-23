"""product_uom_conversions_direction — EP-ERP-01-03: añade columna direction.

La tabla `product_uom_conversions` ya existe (mig 097). Esta migración añade
la columna `direction` (TEXT, nullable) para indicar el sentido canónico de la
conversión: 'base_to_alt' | 'alt_to_base' | 'bidirectional'.

Revision ID: 20260514_106
Revises: 20260514_105
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260514_106"
down_revision: str = "20260514_105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "product_uom_conversions",
        sa.Column(
            "direction",
            sa.Text(),
            nullable=True,
            comment="Sentido canónico: base_to_alt | alt_to_base | bidirectional",
        ),
    )
    op.create_check_constraint(
        "ck_uom_conv_direction",
        "product_uom_conversions",
        "direction IS NULL OR direction IN ('base_to_alt','alt_to_base','bidirectional')",
    )


def downgrade() -> None:
    op.drop_constraint("ck_uom_conv_direction", "product_uom_conversions", type_="check")
    op.drop_column("product_uom_conversions", "direction")
