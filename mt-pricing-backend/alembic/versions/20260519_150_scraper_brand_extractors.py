"""scraper_brand_extractors — JSON attribute-mapping generado por LLM por marca × marketplace.

Revision ID: 20260519_150
Revises: 20260519_149
Create Date: 2026-05-19

Tabla:
- ``scraper_brand_extractors`` — mapeo JSON de atributos Amazon → schema canónico,
  generado una vez por Claude por marca × marketplace y reutilizado sin LLM en
  cada monitoring scrape posterior.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260519_150"
down_revision: str = "20260519_149"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scraper_brand_extractors",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "brand_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("competitor_brands.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("marketplace", sa.String(32), nullable=False),
        # JSON attribute map: {"Amazon label": {"field": "canonical_field", "type": "str|float|int"}}
        sa.Column(
            "attribute_map",
            postgresql.JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        # Sample ASINs used to generate the mapping
        sa.Column(
            "sample_asins",
            postgresql.ARRAY(sa.Text),
            nullable=False,
            server_default=sa.text("'{}'::text[]"),
        ),
        sa.Column("generated_by", sa.String(100), nullable=True),  # "claude-haiku-4-5"
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        sa.Column(
            "last_used_at",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
        # Tracks how often the mapping produced non-empty specs (0.0–1.0)
        sa.Column(
            "hit_rate",
            sa.Numeric(5, 4),
            nullable=False,
            server_default=sa.text("0"),
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
        sa.UniqueConstraint("brand_id", "marketplace", name="uq_brand_extractor"),
        sa.CheckConstraint(
            "marketplace IN ('amazon_uae', 'noon_uae')",
            name="ck_brand_extractor_marketplace",
        ),
    )

    op.create_index(
        "ix_brand_extractor_brand_marketplace",
        "scraper_brand_extractors",
        ["brand_id", "marketplace"],
    )

    op.execute("""
        CREATE OR REPLACE FUNCTION scraper_brand_extractors_updated_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$
    """)

    op.execute("""
        CREATE TRIGGER trg_scraper_brand_extractors_updated_at
        BEFORE UPDATE ON scraper_brand_extractors
        FOR EACH ROW EXECUTE FUNCTION scraper_brand_extractors_updated_at()
    """)


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_scraper_brand_extractors_updated_at ON scraper_brand_extractors"
    )
    op.execute("DROP FUNCTION IF EXISTS scraper_brand_extractors_updated_at()")
    op.drop_index("ix_brand_extractor_brand_marketplace", table_name="scraper_brand_extractors")
    op.drop_table("scraper_brand_extractors")
