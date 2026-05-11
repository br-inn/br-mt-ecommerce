"""divisions — eje ortogonal de catálogo (Hidrosanitario / Industrial).

Stage 3 — Wave 11 (catalog hierarchy refinement):

Un mismo SKU puede aparecer en varias divisiones del catálogo MT
(Hidrosanitario, Industrial, futuras). Modelado como M:N para evitar
duplicación de productos por canal.

- Crea tabla ``divisions`` (catálogo cerrado, seed inicial 2 filas).
- Crea junction ``product_divisions`` (M:N).
- Reutiliza el permiso ``admin:taxonomy`` (mig. 042) para gestión.

Revision ID: 20260509_044
Revises: 20260508_042
Create Date: 2026-05-09

Nota (mig. 049): el down_revision original era "20260508_043" pero la
revisión 043 nunca se creó. 042 fue reconstituida como stub. Chain ajustada
a "042" — el contenido funcional de esta migración no cambia.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "20260509_044"
down_revision: str | None = "20260508_042"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "divisions",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "sort_order",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column(
            "active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
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
    )
    op.create_index("idx_divisions_active", "divisions", ["active"])

    op.create_table(
        "product_divisions",
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "division_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("divisions.id", ondelete="RESTRICT"),
            primary_key=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_product_divisions_division", "product_divisions", ["division_id"]
    )

    # Seed inicial — 2 divisiones MT actuales.
    op.execute(
        """
        INSERT INTO divisions (code, name, description, sort_order)
        VALUES
            ('hidrosanitario', 'Hidrosanitario',
             'División hidrosanitaria — agua fría/caliente, calefacción, sanitarios.', 10),
            ('industrial', 'Industrial',
             'División industrial — vapor, químicos, alta presión, heavy-duty.', 20)
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.drop_index("idx_product_divisions_division", table_name="product_divisions")
    op.drop_table("product_divisions")
    op.drop_index("idx_divisions_active", table_name="divisions")
    op.drop_table("divisions")
