"""US-1B-05-01 — tabla price_reference_excel para parallel run.

Crea la tabla ``price_reference_excel`` que almacena los precios de referencia
provenientes del proceso Excel manual previo. Se usa para el cálculo de diff
en el reporte de parallel run (app vs Excel).

Revision ID: 20260512_073
Revises: 20260512_071
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PG_UUID

from alembic import op

revision: str = "20260512_073"
down_revision: str = "20260512_071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "price_reference_excel",
        sa.Column(
            "id",
            PG_UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("sku", sa.String(128), nullable=False),
        sa.Column("channel", sa.String(64), nullable=False),
        sa.Column(
            "reference_price_aed",
            sa.Numeric(14, 4),
            nullable=False,
        ),
        sa.Column(
            "loaded_at",
            sa.DateTime(timezone=True),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )

    # Índice para lookup por fecha de carga (usado en el diff diario)
    op.create_index(
        "idx_price_reference_excel_loaded_at",
        "price_reference_excel",
        ["loaded_at"],
    )

    # Índice para lookup por sku+canal
    op.create_index(
        "idx_price_reference_excel_sku_channel",
        "price_reference_excel",
        ["sku", "channel"],
    )


def downgrade() -> None:
    op.drop_index("idx_price_reference_excel_sku_channel", table_name="price_reference_excel")
    op.drop_index("idx_price_reference_excel_loaded_at", table_name="price_reference_excel")
    op.drop_table("price_reference_excel")
