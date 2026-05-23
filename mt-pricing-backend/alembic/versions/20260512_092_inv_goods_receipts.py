"""inv_goods_receipts — tabla goods_receipts (EP-INV-01 / US-INV-01-01).

Revision ID: 092
Revises: 091
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision = "092"
down_revision = "091"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "goods_receipts",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "po_line_id",
            sa.UUID(),
            sa.ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty_received", sa.Numeric(12, 3), nullable=False),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "received_by",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("actual_unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "actual_breakdown",
            JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("map_before", sa.Numeric(18, 4), nullable=True),
        sa.Column("map_after", sa.Numeric(18, 4), nullable=True),
        sa.Column(
            "fx_rate_id",
            sa.UUID(),
            sa.ForeignKey("fx_rates.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("qty_received > 0", name="ck_gr_qty_received_pos"),
        sa.CheckConstraint(
            "status IN ('pending','processed','error')",
            name="ck_gr_status",
        ),
    )

    op.create_index("idx_gr_po_line", "goods_receipts", ["po_line_id"])
    op.create_index(
        "idx_gr_status_pending",
        "goods_receipts",
        ["status"],
        postgresql_where=sa.text("status = 'pending'"),
    )
    op.create_index(
        "idx_gr_received_at",
        "goods_receipts",
        [sa.text("received_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_gr_received_at", table_name="goods_receipts")
    op.drop_index("idx_gr_status_pending", table_name="goods_receipts")
    op.drop_index("idx_gr_po_line", table_name="goods_receipts")
    op.drop_table("goods_receipts")
