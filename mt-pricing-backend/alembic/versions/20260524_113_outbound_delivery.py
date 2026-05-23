"""Outbound Deliveries + lines (US-ERP-04-04).

Revision ID: 20260524_113
Revises: 20260524_112
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "20260524_113"
down_revision = "20260524_112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # outbound_deliveries
    # ------------------------------------------------------------------
    op.create_table(
        "outbound_deliveries",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("delivery_number", sa.Text(), nullable=False),
        sa.Column(
            "so_id",
            sa.UUID(),
            sa.ForeignKey("sales_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            sa.UUID(),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending_pick'"),
        ),
        sa.Column(
            "partial_delivery_allowed", sa.Boolean(), nullable=False, server_default=sa.text("true")
        ),
        sa.Column("shipped_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbound_deliveries"),
        sa.UniqueConstraint("delivery_number", name="uq_delivery_number"),
        sa.CheckConstraint(
            "status IN ('pending_pick','picking','packed','goods_issued','cancelled')",
            name="ck_delivery_status",
        ),
    )
    op.create_index("idx_delivery_so_id", "outbound_deliveries", ["so_id"])
    op.create_index("idx_delivery_status", "outbound_deliveries", ["status"])

    # ------------------------------------------------------------------
    # outbound_delivery_lines
    # ------------------------------------------------------------------
    op.create_table(
        "outbound_delivery_lines",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "delivery_id",
            sa.UUID(),
            sa.ForeignKey("outbound_deliveries.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "so_line_id",
            sa.UUID(),
            sa.ForeignKey("sales_order_lines.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty_planned", sa.Numeric(18, 4), nullable=False),
        sa.Column("qty_picked", sa.Numeric(18, 4), nullable=False, server_default=sa.text("0")),
        sa.Column(
            "lot_id",
            sa.UUID(),
            sa.ForeignKey("inventory_lots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "location_id",
            sa.UUID(),
            sa.ForeignKey("warehouse_locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_outbound_delivery_lines"),
    )
    op.create_index("idx_del_line_delivery", "outbound_delivery_lines", ["delivery_id"])
    op.create_index("idx_del_line_sku", "outbound_delivery_lines", ["product_sku"])


def downgrade() -> None:
    op.drop_table("outbound_delivery_lines")
    op.drop_table("outbound_deliveries")
