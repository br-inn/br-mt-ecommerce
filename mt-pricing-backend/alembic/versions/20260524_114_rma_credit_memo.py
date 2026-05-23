"""RMA headers/lines + credit memos (US-ERP-04-05).

Revision ID: 20260524_114
Revises: 20260524_113
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "20260524_114"
down_revision = "20260524_113"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # rma_headers
    # ------------------------------------------------------------------
    op.create_table(
        "rma_headers",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("rma_number", sa.Text(), nullable=False),
        sa.Column(
            "original_so_id",
            sa.UUID(),
            sa.ForeignKey("sales_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column(
            "return_type",
            sa.Text(),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'requested'"),
        ),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rma_headers"),
        sa.UniqueConstraint("rma_number", name="uq_rma_number"),
        sa.CheckConstraint(
            "return_type IN ('full','partial','damaged','wrong_item')",
            name="ck_rma_return_type",
        ),
        sa.CheckConstraint(
            "status IN ('requested','approved','goods_received','credit_issued','closed','rejected')",
            name="ck_rma_status",
        ),
    )
    op.create_index("idx_rma_so_id", "rma_headers", ["original_so_id"])
    op.create_index("idx_rma_customer", "rma_headers", ["customer_id"])
    op.create_index("idx_rma_status", "rma_headers", ["status"])

    # ------------------------------------------------------------------
    # rma_lines
    # ------------------------------------------------------------------
    op.create_table(
        "rma_lines",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "rma_id",
            sa.UUID(),
            sa.ForeignKey("rma_headers.id", ondelete="CASCADE"),
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
        sa.Column("qty_returned", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "lot_id",
            sa.UUID(),
            sa.ForeignKey("inventory_lots.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "condition",
            sa.Text(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_rma_lines"),
        sa.CheckConstraint(
            "condition IN ('resalable','damaged','to_dispose')",
            name="ck_rma_line_condition",
        ),
    )
    op.create_index("idx_rma_line_rma_id", "rma_lines", ["rma_id"])
    op.create_index("idx_rma_line_sku", "rma_lines", ["product_sku"])

    # ------------------------------------------------------------------
    # credit_memos
    # ------------------------------------------------------------------
    op.create_table(
        "credit_memos",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("memo_number", sa.Text(), nullable=False),
        sa.Column(
            "rma_id",
            sa.UUID(),
            sa.ForeignKey("rma_headers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'AED'")),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_credit_memos"),
        sa.UniqueConstraint("memo_number", name="uq_credit_memo_number"),
        sa.CheckConstraint(
            "status IN ('pending','approved','applied','cancelled')",
            name="ck_credit_memo_status",
        ),
    )
    op.create_index("idx_credit_memo_rma", "credit_memos", ["rma_id"])
    op.create_index("idx_credit_memo_customer", "credit_memos", ["customer_id"])


def downgrade() -> None:
    op.drop_table("credit_memos")
    op.drop_table("rma_lines")
    op.drop_table("rma_headers")
