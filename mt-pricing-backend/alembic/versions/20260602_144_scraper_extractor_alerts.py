"""scraper_extractor_alerts — tabla de alertas de degradación de hit_rate (US-SCR-05-04).

Revision ID: 20260602_144
Revises: 20260602_143
Create Date: 2026-05-20

Crea ``scraper_extractor_alerts`` para registrar cuando el hit_rate de un
BrandExtractor cae > 20pp respecto a la baseline de 7 días.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260602_144"
down_revision = "20260602_143"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "scraper_extractor_alerts",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("brand_id", sa.UUID(), nullable=False),
        sa.Column("marketplace", sa.String(32), nullable=False),
        sa.Column("triggered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hit_rate_now", sa.Numeric(5, 4), nullable=False),
        sa.Column("hit_rate_baseline", sa.Numeric(5, 4), nullable=False),
        sa.Column("delta_pp", sa.Numeric(6, 2), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_by", sa.UUID(), nullable=True),
        sa.ForeignKeyConstraint(
            ["brand_id"], ["competitor_brands.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["resolved_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_extractor_alerts_brand_mkt_resolved",
        "scraper_extractor_alerts",
        ["brand_id", "marketplace", "resolved_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_extractor_alerts_brand_mkt_resolved", table_name="scraper_extractor_alerts")
    op.drop_table("scraper_extractor_alerts")
