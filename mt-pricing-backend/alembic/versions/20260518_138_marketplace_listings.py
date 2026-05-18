"""Create product_marketplace_listings table.

Revision ID: 20260518138a
Revises: 20260518137a
Create Date: 2026-05-18
"""
from __future__ import annotations
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, ARRAY

revision = "20260518138a"
down_revision = "20260518137a"
branch_labels = None
depends_on = None

MARKETPLACES = ("amazon_uae", "noon_uae", "shopify_storefront")
STATUSES = ("draft", "ready", "published", "paused")


def upgrade() -> None:
    op.create_table(
        "product_marketplace_listings",
        sa.Column("id", sa.Text(), primary_key=True,
                  server_default=sa.text("gen_random_uuid()::text")),
        sa.Column("product_sku", sa.Text(),
                  sa.ForeignKey("products.sku", ondelete="CASCADE"), nullable=False),
        sa.Column("marketplace", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("listing_title", sa.Text(), nullable=True),
        sa.Column("listing_description", sa.Text(), nullable=True),
        sa.Column("bullet_points", ARRAY(sa.Text()), nullable=False,
                  server_default=sa.text("'{}'::text[]")),
        sa.Column("search_keywords", sa.Text(), nullable=True),
        sa.Column("extra", JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("ai_generated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ai_model", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
    )
    op.create_unique_constraint(
        "uq_marketplace_listings_sku_marketplace",
        "product_marketplace_listings",
        ["product_sku", "marketplace"],
    )
    op.create_check_constraint(
        "ck_marketplace_listings_marketplace",
        "product_marketplace_listings",
        f"marketplace IN {tuple(MARKETPLACES)}",
    )
    op.create_check_constraint(
        "ck_marketplace_listings_status",
        "product_marketplace_listings",
        f"status IN {tuple(STATUSES)}",
    )
    op.create_index("idx_marketplace_listings_sku", "product_marketplace_listings", ["product_sku"])
    op.create_index("idx_marketplace_listings_marketplace", "product_marketplace_listings", ["marketplace"])
    op.create_index("idx_marketplace_listings_status", "product_marketplace_listings", ["status"])


def downgrade() -> None:
    op.drop_table("product_marketplace_listings")
