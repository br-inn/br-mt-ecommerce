"""ATP checking rules + stock reservations (US-ERP-04-02).

Revision ID: 20260524_111
Revises: 20260524_110
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "20260524_111"
down_revision = "20260524_110"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # atp_checking_rules
    # ------------------------------------------------------------------
    op.create_table(
        "atp_checking_rules",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column(
            "include_safety_stock", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column(
            "include_planned_receipts", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column(
            "include_qa_stock", sa.Boolean(), nullable=False, server_default=sa.text("false")
        ),
        sa.Column("horizon_days", sa.Integer(), nullable=False, server_default=sa.text("30")),
        sa.PrimaryKeyConstraint("id", name="pk_atp_checking_rules"),
    )
    op.create_index("idx_atp_rule_sku", "atp_checking_rules", ["product_sku"])

    # ------------------------------------------------------------------
    # stock_reservations
    # ------------------------------------------------------------------
    op.create_table(
        "stock_reservations",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "so_line_id",
            sa.UUID(),
            sa.ForeignKey("sales_order_lines.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            sa.UUID(),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "reserved_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'active'"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_stock_reservations"),
        sa.CheckConstraint(
            "status IN ('active','consumed','expired','cancelled')",
            name="ck_reservation_status",
        ),
    )
    op.create_index("idx_reservation_so_line", "stock_reservations", ["so_line_id"])
    op.create_index("idx_reservation_sku_status", "stock_reservations", ["product_sku", "status"])
    op.create_index("idx_reservation_warehouse", "stock_reservations", ["warehouse_id"])


def downgrade() -> None:
    op.drop_table("stock_reservations")
    op.drop_table("atp_checking_rules")
