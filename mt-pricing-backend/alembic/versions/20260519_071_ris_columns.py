"""ris_columns — reverse_image_hits/searched_at/provider en competitor_listings (US-F15-02-03).

Revision ID: 071
Revises: 070
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "071"
down_revision = "070"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "competitor_listings",
        sa.Column(
            "reverse_image_hits",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
    )
    op.add_column(
        "competitor_listings",
        sa.Column("reverse_image_searched_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "competitor_listings",
        sa.Column("reverse_image_provider", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("competitor_listings", "reverse_image_provider")
    op.drop_column("competitor_listings", "reverse_image_searched_at")
    op.drop_column("competitor_listings", "reverse_image_hits")
