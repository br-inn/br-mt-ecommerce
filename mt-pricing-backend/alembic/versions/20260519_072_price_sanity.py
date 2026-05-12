"""price_sanity — price_calibration_ranges + sanity cols en competitor_listings (US-F15-02-04).

Revision ID: 072
Revises: 071
Create Date: 2026-05-19
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "072"
down_revision = "071"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Nueva tabla price_calibration_ranges
    # ------------------------------------------------------------------
    op.create_table(
        "price_calibration_ranges",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("category_id", sa.String(64), nullable=False),
        sa.Column("expected_min_p10", sa.Numeric(14, 4), nullable=False),
        sa.Column("expected_max_p90", sa.Numeric(14, 4), nullable=False),
        sa.Column(
            "currency",
            sa.CHAR(3),
            nullable=False,
            server_default="AED",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "category_id",
            "currency",
            name="uq_price_calibration_ranges_category_currency",
        ),
    )

    # ------------------------------------------------------------------
    # Columnas de sanity check en competitor_listings
    # ------------------------------------------------------------------
    op.add_column(
        "competitor_listings",
        sa.Column(
            "price_too_low",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "competitor_listings",
        sa.Column(
            "price_too_high",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "competitor_listings",
        sa.Column(
            "sanity_check_skipped",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("competitor_listings", "sanity_check_skipped")
    op.drop_column("competitor_listings", "price_too_high")
    op.drop_column("competitor_listings", "price_too_low")
    op.drop_table("price_calibration_ranges")
