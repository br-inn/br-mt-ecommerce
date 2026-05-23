"""inv_inventory_positions — tabla inventory_positions (EP-INV-01 / US-INV-01-01).

`total_stock_value_aed` es GENERATED ALWAYS AS (qty_on_hand * map_aed) STORED.

Revision ID: 094
Revises: 093
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "094"
down_revision = "093"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "inventory_positions",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("supplier_code", sa.String(64), nullable=False),
        sa.Column(
            "scheme_code",
            sa.String(32),
            sa.ForeignKey("schemes.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "qty_on_hand",
            sa.Numeric(12, 3),
            nullable=False,
            server_default=sa.text("0"),
        ),
        sa.Column("map_aed", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "total_stock_value_aed",
            sa.Numeric(18, 4),
            sa.Computed("qty_on_hand * map_aed", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "last_gr_id",
            sa.UUID(),
            sa.ForeignKey("goods_receipts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("last_updated_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("sku", "supplier_code", "scheme_code", name="uq_inventory_positions"),
    )

    op.create_index("idx_inv_pos_sku", "inventory_positions", ["sku"])


def downgrade() -> None:
    op.drop_index("idx_inv_pos_sku", table_name="inventory_positions")
    op.drop_table("inventory_positions")
