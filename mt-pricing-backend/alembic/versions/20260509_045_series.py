"""series — entidad rica de marketing (tier, pressure_rating, banner, certs default).

Stage 3 — Wave 11 (catalog hierarchy refinement):

Las páginas reales del catálogo MT muestran que ``series`` es mucho más que
un agrupador comercial: tiene tier nominal (PLATINUM/GOLD/SILVER/BRONZE),
pressure_rating (PN40/PN30/...), color identity, certificaciones default
y bullets de spec compartidos por todos los parent products de la serie.

Tablas nuevas:
- ``series_tiers``: vocab cerrado (platinum, gold, silver, bronze, n_a).
- ``series``: entidad principal con tier_id, pressure_rating_pn, banner_color,
  hero_image_url, description_en, bullets_en, features_tags, sort_order.
- ``series_translations``: ES/AR/EN per-row name/description/bullets.
- ``series_divisions``: M:N — qué series aparecen en qué catálogo.
- ``series_certifications``: M:N — paquete default de certificaciones.

Cambios en ``products``:
- ``series_id`` UUID NULL FK → series (coexiste con TEXT ``series`` durante transición).
- ``display_pair_sku`` TEXT NULL self-FK → products.sku (empareja modelos por
  color, ej. 4295 ↔ 42952). 1:1 simétrico mantenido por convención (se actualizan
  ambos extremos en service layer).

Backfill:
- Inserta filas distintas en ``series`` desde ``products.series`` no-vacíos.
- Actualiza ``products.series_id`` por código.

Seeds:
- 5 tiers (platinum, gold, silver, bronze, n_a).
- Series base se crearán por importer/admin; aquí solo el backfill desde TEXT.

Revision ID: 20260509_045
Revises: 20260509_044
Create Date: 2026-05-09
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import ARRAY as PgARRAY
from sqlalchemy.dialects.postgresql import UUID as PgUUID

revision: str = "20260509_045"
down_revision: str | None = "20260509_044"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # series_tiers — vocab cerrado
    # ------------------------------------------------------------------
    op.create_table(
        "series_tiers",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "rank",
            sa.SmallInteger(),
            nullable=False,
            server_default=sa.text("99"),
        ),
        sa.Column("display_color", sa.Text(), nullable=True),
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
    op.execute(
        """
        INSERT INTO series_tiers (code, name, rank, display_color)
        VALUES
            ('platinum', 'Platinum', 1, '#E5004C'),
            ('gold',     'Gold',     2, '#E2B233'),
            ('silver',   'Silver',   3, '#A8A8A8'),
            ('bronze',   'Bronze',   4, '#A57052'),
            ('n_a',      'N/A',     99, '#6B7280')
        ON CONFLICT (code) DO NOTHING;
        """
    )

    # ------------------------------------------------------------------
    # series — entidad principal
    # ------------------------------------------------------------------
    op.create_table(
        "series",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("code", sa.Text(), nullable=False, unique=True),
        sa.Column("name_en", sa.Text(), nullable=False),
        sa.Column(
            "tier_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("series_tiers.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("pressure_rating_pn", sa.Integer(), nullable=True),
        sa.Column("temperature_min_c", sa.Integer(), nullable=True),
        sa.Column("temperature_max_c", sa.Integer(), nullable=True),
        sa.Column("banner_color", sa.Text(), nullable=True),
        sa.Column("hero_image_url", sa.Text(), nullable=True),
        sa.Column("description_en", sa.Text(), nullable=True),
        sa.Column(
            "bullets_en",
            PgARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column(
            "features_tags",
            PgARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
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
    op.create_index("idx_series_tier", "series", ["tier_id"])
    op.create_index("idx_series_active", "series", ["active"])
    op.create_index(
        "idx_series_pressure_rating", "series", ["pressure_rating_pn"]
    )

    # ------------------------------------------------------------------
    # series_translations — ES / AR / EN
    # ------------------------------------------------------------------
    op.create_table(
        "series_translations",
        sa.Column(
            "series_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("lang", sa.String(2), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "bullets",
            PgARRAY(sa.Text()),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
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

    # ------------------------------------------------------------------
    # series_divisions — qué series aparecen en qué catálogo PDF
    # ------------------------------------------------------------------
    op.create_table(
        "series_divisions",
        sa.Column(
            "series_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="CASCADE"),
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
        "idx_series_divisions_division", "series_divisions", ["division_id"]
    )

    # ------------------------------------------------------------------
    # series_certifications — paquete default de certs por serie
    # ------------------------------------------------------------------
    op.create_table(
        "series_certifications",
        sa.Column(
            "series_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "certification_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("certifications.id", ondelete="RESTRICT"),
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
        "idx_series_certifications_cert",
        "series_certifications",
        ["certification_id"],
    )

    # ------------------------------------------------------------------
    # products.series_id + display_pair_sku
    # ------------------------------------------------------------------
    op.add_column(
        "products",
        sa.Column(
            "series_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("series.id", ondelete="RESTRICT"),
            nullable=True,
        ),
    )
    op.create_index("idx_products_series_id", "products", ["series_id"])

    op.add_column(
        "products",
        sa.Column(
            "display_pair_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_products_display_pair_sku", "products", ["display_pair_sku"]
    )

    # ------------------------------------------------------------------
    # Backfill: distinct series TEXT → series rows
    # ------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO series (code, name_en)
        SELECT DISTINCT
            lower(regexp_replace(btrim(series), '\\s+', '_', 'g')) AS code,
            btrim(series) AS name_en
        FROM products
        WHERE series IS NOT NULL AND btrim(series) <> ''
        ON CONFLICT (code) DO NOTHING;
        """
    )
    op.execute(
        """
        UPDATE products p
        SET series_id = s.id
        FROM series s
        WHERE p.series IS NOT NULL
          AND btrim(p.series) <> ''
          AND lower(regexp_replace(btrim(p.series), '\\s+', '_', 'g')) = s.code
          AND p.series_id IS NULL;
        """
    )


def downgrade() -> None:
    op.drop_index("idx_products_display_pair_sku", table_name="products")
    op.drop_column("products", "display_pair_sku")
    op.drop_index("idx_products_series_id", table_name="products")
    op.drop_column("products", "series_id")

    op.drop_index(
        "idx_series_certifications_cert", table_name="series_certifications"
    )
    op.drop_table("series_certifications")

    op.drop_index("idx_series_divisions_division", table_name="series_divisions")
    op.drop_table("series_divisions")

    op.drop_table("series_translations")

    op.drop_index("idx_series_pressure_rating", table_name="series")
    op.drop_index("idx_series_active", table_name="series")
    op.drop_index("idx_series_tier", table_name="series")
    op.drop_table("series")

    op.drop_table("series_tiers")
