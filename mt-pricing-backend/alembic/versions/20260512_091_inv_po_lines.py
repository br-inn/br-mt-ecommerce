"""inv_po_lines — tabla purchase_order_lines (EP-INV-01 / US-INV-01-01).

Revision ID: 091
Revises: 090
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "091"
down_revision = "090"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_order_lines",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "po_id",
            sa.UUID(),
            sa.ForeignKey("purchase_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scheme_code",
            sa.String(32),
            sa.ForeignKey("schemes.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty_ordered", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "qty_received",
            sa.Numeric(12, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "landed_cost_breakdown",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
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
        sa.CheckConstraint("qty_ordered > 0", name="ck_pol_qty_ordered_pos"),
        sa.CheckConstraint("qty_received >= 0", name="ck_pol_qty_received_nonneg"),
        sa.CheckConstraint("unit_price >= 0", name="ck_pol_unit_price_nonneg"),
    )

    op.create_index("idx_pol_po", "purchase_order_lines", ["po_id"])
    op.create_index("idx_pol_sku", "purchase_order_lines", ["sku"])


def downgrade() -> None:
    op.drop_index("idx_pol_sku", table_name="purchase_order_lines")
    op.drop_index("idx_pol_po", table_name="purchase_order_lines")
    op.drop_table("purchase_order_lines")
