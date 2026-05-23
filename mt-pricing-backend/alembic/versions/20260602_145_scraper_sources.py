"""scraper_sources — motor de scraper configurable data-driven (Scraper Source Builder F1).

Revision ID: 20260602_145
Revises: 20260602_144
Create Date: 2026-05-20

Crea las tablas del módulo Scraper Source Builder:
- scraper_sources: definición configurable de un sitio a scrapear
- scraper_source_recipes: receta de extracción versionada (una is_live por source)
- scraper_source_test_runs: resultados de validación de recetas
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260602_145"
down_revision = "20260602_144"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    destination_profile = postgresql.ENUM(
        "competitor_price", "product_data", name="scraper_destination_profile"
    )
    fetch_mode = postgresql.ENUM("static", "headless", "stealth", name="scraper_fetch_mode")
    source_status = postgresql.ENUM(
        "draft",
        "testing",
        "active",
        "disabled",
        "degraded",
        name="scraper_source_status",
    )
    validation_status = postgresql.ENUM(
        "unvalidated",
        "passing",
        "failing",
        name="scraper_recipe_validation_status",
    )
    destination_profile.create(bind, checkfirst=True)
    fetch_mode.create(bind, checkfirst=True)
    source_status.create(bind, checkfirst=True)
    validation_status.create(bind, checkfirst=True)

    op.create_table(
        "scraper_sources",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("slug", sa.String(80), nullable=False),
        sa.Column("base_url", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "destination_profile",
            postgresql.ENUM(name="scraper_destination_profile", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "fetch_mode",
            postgresql.ENUM(name="scraper_fetch_mode", create_type=False),
            nullable=False,
            server_default=sa.text("'static'::scraper_fetch_mode"),
        ),
        sa.Column(
            "status",
            postgresql.ENUM(name="scraper_source_status", create_type=False),
            nullable=False,
            server_default=sa.text("'draft'::scraper_source_status"),
        ),
        sa.Column("competitor_brand_id", sa.UUID(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("generated_by", sa.String(100), nullable=True),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["competitor_brand_id"], ["competitor_brands.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_scraper_sources_slug"),
    )

    op.create_table(
        "scraper_source_recipes",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("is_live", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "recipe", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column(
            "validation_status",
            postgresql.ENUM(name="scraper_recipe_validation_status", create_type=False),
            nullable=False,
            server_default=sa.text("'unvalidated'::scraper_recipe_validation_status"),
        ),
        sa.Column(
            "has_unapproved_snippet", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["scraper_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("source_id", "version", name="uq_recipe_source_version"),
    )
    op.create_index(
        "uq_recipe_one_live_per_source",
        "scraper_source_recipes",
        ["source_id"],
        unique=True,
        postgresql_where=sa.text("is_live"),
    )

    op.create_table(
        "scraper_source_test_runs",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_id", sa.UUID(), nullable=False),
        sa.Column("recipe_id", sa.UUID(), nullable=False),
        sa.Column("test_url", sa.Text(), nullable=False),
        sa.Column("html_snapshot_ref", sa.Text(), nullable=True),
        sa.Column(
            "extracted", postgresql.JSONB(), nullable=False, server_default=sa.text("'[]'::jsonb")
        ),
        sa.Column(
            "field_results",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["source_id"], ["scraper_sources.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["recipe_id"], ["scraper_source_recipes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_source_test_runs_source", "scraper_source_test_runs", ["source_id", "created_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_source_test_runs_source", table_name="scraper_source_test_runs")
    op.drop_table("scraper_source_test_runs")
    op.drop_index("uq_recipe_one_live_per_source", table_name="scraper_source_recipes")
    op.drop_table("scraper_source_recipes")
    op.drop_table("scraper_sources")
    for enum_name in (
        "scraper_recipe_validation_status",
        "scraper_source_status",
        "scraper_fetch_mode",
        "scraper_destination_profile",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
