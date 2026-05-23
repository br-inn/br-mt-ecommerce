"""competitor_brands table + competitor_brand_id FK en competitor_listings.

Revision ID: 20260530132
Revises: 20260515_135
Create Date: 2026-05-30
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "20260530132"
down_revision = "20260515_135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "competitor_brands",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("amazon_search_term", sa.String(200), nullable=True),
        sa.Column("amazon_dept", sa.String(100), server_default="industrial", nullable=False),
        sa.Column("amazon_category_node", sa.String(50), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_scraped_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ux_competitor_brands_name",
        "competitor_brands",
        [sa.text("lower(name)")],
        unique=True,
    )

    op.add_column(
        "competitor_listings",
        sa.Column("competitor_brand_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_competitor_listings_brand",
        "competitor_listings",
        "competitor_brands",
        ["competitor_brand_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_competitor_listings_brand_id",
        "competitor_listings",
        ["competitor_brand_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_competitor_listings_brand_id", table_name="competitor_listings")
    op.drop_constraint("fk_competitor_listings_brand", "competitor_listings", type_="foreignkey")
    op.drop_column("competitor_listings", "competitor_brand_id")
    op.drop_index("ux_competitor_brands_name", table_name="competitor_brands")
    op.drop_table("competitor_brands")
