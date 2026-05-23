"""tech_tables — Wave 6: structured technical tables (matrix-style data).

Cubre 3 tipos de tablas estructuradas que viven hoy en datasheets PDF:
- ``materials_matrix`` — componente x material con observaciones.
- ``dimensions_by_dn`` — DN x medidas (L, H, K, etc.).
- ``pressure_temperature`` — temperatura x presión máxima.

Modelo: una fila ``product_tech_tables`` por producto y kind, con ``data jsonb``
validada en application layer (Pydantic) según ``schema_version``.

Slot 039.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260508_039"
down_revision: str | None = "20260508_038"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE tech_table_kind AS ENUM (
                'materials_matrix','dimensions_by_dn','pressure_temperature'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )
    op.execute(
        """
        DO $$ BEGIN
            CREATE TYPE tech_table_source AS ENUM (
                'manual','imported_pdf','imported_excel'
            );
        EXCEPTION WHEN duplicate_object THEN null;
        END $$;
        """
    )

    op.create_table(
        "product_tech_tables",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.Text,
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "kind",
            postgresql.ENUM(
                "materials_matrix",
                "dimensions_by_dn",
                "pressure_temperature",
                name="tech_table_kind",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "schema_version",
            sa.Text,
            nullable=False,
            server_default=sa.text("'v1'"),
        ),
        sa.Column(
            "source",
            postgresql.ENUM(
                "manual",
                "imported_pdf",
                "imported_excel",
                name="tech_table_source",
                create_type=False,
            ),
            nullable=False,
            server_default=sa.text("'manual'"),
        ),
        sa.Column(
            "data",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("source_asset_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("product_sku", "kind", name="uq_product_tech_tables_sku_kind"),
    )
    op.create_index("idx_product_tech_tables_sku", "product_tech_tables", ["product_sku"])
    op.create_index("idx_product_tech_tables_kind", "product_tech_tables", ["kind"])


def downgrade() -> None:
    op.drop_index("idx_product_tech_tables_kind", table_name="product_tech_tables")
    op.drop_index("idx_product_tech_tables_sku", table_name="product_tech_tables")
    op.drop_table("product_tech_tables")
    op.execute("DROP TYPE IF EXISTS tech_table_source")
    op.execute("DROP TYPE IF EXISTS tech_table_kind")
