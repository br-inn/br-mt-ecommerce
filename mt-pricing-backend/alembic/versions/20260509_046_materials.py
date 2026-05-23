"""materials — vocabulario curado del agrupador material del catálogo.

Stage 3 — Wave 11 (catalog hierarchy refinement):

Material es **agrupador de presentación** del catálogo PDF (1.1 ACERO INOX,
1.2 LATÓN, 1.3 FUNDICIÓN), no nivel taxonómico. Mantenemos la columna
``products.material`` TEXT para libre + ``material_id`` FK opcional contra
vocabulario curado para el agrupador del PDF y filtros de catálogo.

- Crea tabla ``materials`` (id, code, name, family_kind, sort_order, …).
- Seed inicial con los 6 grupos canónicos del catálogo MT.
- Añade ``products.material_id`` FK NULL (transición — coexiste con TEXT).
- Backfill desde distinct ``products.material`` no-vacíos.

Revision ID: 20260509_046
Revises: 20260509_045
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID as PgUUID

from alembic import op

revision: str = "20260509_046"
down_revision: str | None = "20260509_045"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "materials",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("family_kind", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
    op.create_index("idx_materials_active", "materials", ["active"])

    op.execute(
        """
        INSERT INTO materials (code, name, family_kind, sort_order)
        VALUES
            ('laton',              'Latón',             'metal',    10),
            ('acero_inoxidable',   'Acero inoxidable',  'metal',    20),
            ('fundicion',          'Fundición',         'metal',    30),
            ('galvanizado',        'Galvanizado',       'metal',    40),
            ('plastico_pvc',       'Plástico / PVC',    'polymer',  50),
            ('ppr',                'PPR',               'polymer',  60)
        ON CONFLICT (code) DO NOTHING;
        """
    )

    op.add_column(
        "products",
        sa.Column(
            "material_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("materials.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("idx_products_material_id", "products", ["material_id"])

    # Backfill: distinct material TEXT → materials rows; map FK.
    op.execute(
        """
        INSERT INTO materials (code, name)
        SELECT DISTINCT
            lower(regexp_replace(btrim(material), '\\s+', '_', 'g')) AS code,
            btrim(material) AS name
        FROM products
        WHERE material IS NOT NULL AND btrim(material) <> ''
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        UPDATE products p
        SET material_id = m.id
        FROM materials m
        WHERE p.material IS NOT NULL
          AND btrim(p.material) <> ''
          AND lower(regexp_replace(btrim(p.material), '\\s+', '_', 'g')) = m.code
          AND p.material_id IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_index("idx_products_material_id", table_name="products")
    op.drop_column("products", "material_id")
    op.drop_index("idx_materials_active", table_name="materials")
    op.drop_table("materials")
