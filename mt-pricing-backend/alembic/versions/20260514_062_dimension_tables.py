"""Fase 3 — Tablas técnicas: dimension_columns / dimension_rows / dimension_cells.

Modelo de tabla de dimensiones por familia (PDF §9). Cada familia define
un set de columnas (DN, A, B, H, F, peso…) reutilizable; cada producto
añade filas (una por tamaño / variante de actuación); cada celda cruza
fila × columna con un valor numérico o textual.

- ``dimension_columns``: definición por familia. UNIQUE (family_id, code).
- ``dimension_rows``: filas por producto. Incluye ``size_label`` (texto
  libre tipo "DN50") + ``dn`` numérico (filtrable) + FK opcional a
  ``actuation_codes`` (variante de actuación dentro del mismo tamaño).
- ``dimension_cells``: celdas con UNIQUE (row_id, column_id) y CHECK
  garantizando que al menos uno de ``value_number`` / ``value_text``
  esté relleno.

Revision ID: 20260514_062
Revises: 20260514_061
Create Date: 2026-05-14
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260514_062"
down_revision: str | None = "20260514_061"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. dimension_columns — definición de columnas por familia
    # ------------------------------------------------------------------
    op.create_table(
        "dimension_columns",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "family_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("families.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("label_en", sa.Text(), nullable=False),
        sa.Column("unit", sa.Text(), nullable=True),
        sa.Column(
            "order_index",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.UniqueConstraint("family_id", "code", name="uq_dimension_columns_family_code"),
    )
    op.create_index(
        "ix_dimension_columns_family",
        "dimension_columns",
        ["family_id"],
    )

    # ------------------------------------------------------------------
    # 2. dimension_rows — filas por producto
    # ------------------------------------------------------------------
    op.create_table(
        "dimension_rows",
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
        sa.Column("size_label", sa.Text(), nullable=True),
        sa.Column("dn", sa.Integer(), nullable=True),
        sa.Column(
            "actuation_code_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("actuation_codes.id", ondelete="SET NULL"),
            nullable=True,
        ),
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
    op.create_index("ix_dr_product", "dimension_rows", ["product_sku"])

    # ------------------------------------------------------------------
    # 3. dimension_cells — celdas valor
    # ------------------------------------------------------------------
    op.create_table(
        "dimension_cells",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "row_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("dimension_rows.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "column_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("dimension_columns.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("value_number", sa.Numeric(18, 6), nullable=True),
        sa.Column("value_text", sa.Text(), nullable=True),
        sa.UniqueConstraint("row_id", "column_id", name="uq_dimension_cells_row_col"),
        sa.CheckConstraint(
            "value_number IS NOT NULL OR value_text IS NOT NULL",
            name="ck_dimension_cells_value_present",
        ),
    )
    op.create_index("ix_dc_row", "dimension_cells", ["row_id"])
    op.create_index("ix_dc_column", "dimension_cells", ["column_id"])


def downgrade() -> None:
    op.drop_index("ix_dc_column", table_name="dimension_cells")
    op.drop_index("ix_dc_row", table_name="dimension_cells")
    op.drop_table("dimension_cells")

    op.drop_index("ix_dr_product", table_name="dimension_rows")
    op.drop_table("dimension_rows")

    op.drop_index("ix_dimension_columns_family", table_name="dimension_columns")
    op.drop_table("dimension_columns")
