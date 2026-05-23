"""Fase 3 — Tablas técnicas: pressure_temperature_points (curva P-T).

Modela la curva presión-temperatura por producto (PDF §9). Cada punto es
(temperatura_c, pressure_max_bar) con ``series_variant_code`` opcional
para discriminar curvas dentro de una misma serie (e.g. PN10/PN16 trims)
y ``condition_en`` para anotaciones libres (e.g. "vapor saturado").

Revision ID: 20260514_063
Revises: 20260514_062
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "20260514_063"
down_revision: str | None = "20260514_062"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "pressure_temperature_points",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("series_variant_code", sa.Text(), nullable=True),
        sa.Column("temperature_c", sa.Numeric(8, 2), nullable=False),
        sa.Column("pressure_max_bar", sa.Numeric(8, 2), nullable=False),
        sa.Column("condition_en", sa.Text(), nullable=True),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_ptp_product", "pressure_temperature_points", ["product_sku"])


def downgrade() -> None:
    op.drop_index("ix_ptp_product", table_name="pressure_temperature_points")
    op.drop_table("pressure_temperature_points")
