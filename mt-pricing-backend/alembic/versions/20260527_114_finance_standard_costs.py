"""EP-ERP-06 US-ERP-06-05 — Standard Cost + Price Purchase Variance.

Revision ID: 20260527_114
Revises: 20260527_113
Create Date: 2026-05-27

Tables: standard_costs, price_variances
Note: product_sku references products.sku (TEXT PK — NUNCA product_id UUID)
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260527_114"
down_revision = "20260527_113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # standard_costs
    # -------------------------------------------------------------------------
    op.create_table(
        "standard_costs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("product_sku", sa.Text(), sa.ForeignKey("products.sku", ondelete="CASCADE"), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("standard_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), server_default="AED", nullable=False),
        sa.Column("cost_type", sa.Text(), server_default="standard", nullable=False),
        sa.Column("valid_from", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "cost_type IN ('standard','planned','actual')",
            name="ck_standard_costs_cost_type",
        ),
        sa.UniqueConstraint("product_sku", "fiscal_year", "cost_type", name="uq_standard_costs_sku_fy_type"),
    )
    op.create_index("ix_standard_costs_sku", "standard_costs", ["product_sku"])
    op.create_index("ix_standard_costs_fy", "standard_costs", ["fiscal_year"])

    # -------------------------------------------------------------------------
    # price_variances
    # -------------------------------------------------------------------------
    op.create_table(
        "price_variances",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("po_line_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_order_lines.id", ondelete="SET NULL"), nullable=True),
        sa.Column("product_sku", sa.Text(), sa.ForeignKey("products.sku", ondelete="CASCADE"), nullable=False),
        sa.Column("standard_cost", sa.Numeric(18, 4), nullable=False),
        sa.Column("actual_cost", sa.Numeric(18, 4), nullable=False),
        # GENERATED ALWAYS AS stored column
        sa.Column("variance_amount", sa.Numeric(18, 4),
                  sa.Computed("actual_cost - standard_cost", persisted=True)),
        sa.Column("variance_pct", sa.Numeric(7, 4), nullable=True),
        sa.Column("period", sa.Integer(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_price_variances_sku", "price_variances", ["product_sku"])
    op.create_index("ix_price_variances_period", "price_variances", ["fiscal_year", "period"])


def downgrade() -> None:
    op.drop_index("ix_price_variances_period", table_name="price_variances")
    op.drop_index("ix_price_variances_sku", table_name="price_variances")
    op.drop_table("price_variances")
    op.drop_index("ix_standard_costs_fy", table_name="standard_costs")
    op.drop_index("ix_standard_costs_sku", table_name="standard_costs")
    op.drop_table("standard_costs")
