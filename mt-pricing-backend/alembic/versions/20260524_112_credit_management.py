"""Credit limits + customer open items (US-ERP-04-03).

Revision ID: 20260524_112
Revises: 20260524_111
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision = "20260524_112"
down_revision = "20260524_111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # customer_credit_limits
    # ------------------------------------------------------------------
    op.create_table(
        "customer_credit_limits",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column("credit_limit", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'AED'")),
        sa.Column(
            "credit_horizon_days", sa.Integer(), nullable=False, server_default=sa.text("30")
        ),
        sa.Column("is_blocked", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("block_reason", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_credit_limits"),
        sa.UniqueConstraint("customer_id", name="uq_credit_limit_customer"),
    )
    op.create_index("idx_credit_limit_customer", "customer_credit_limits", ["customer_id"])

    # ------------------------------------------------------------------
    # customer_open_items
    # ------------------------------------------------------------------
    op.create_table(
        "customer_open_items",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column(
            "so_id",
            sa.UUID(),
            sa.ForeignKey("sales_orders.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("invoice_id", sa.UUID(), nullable=True),
        sa.Column(
            "document_type",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_customer_open_items"),
        sa.CheckConstraint(
            "document_type IN ('so','invoice')",
            name="ck_open_item_doc_type",
        ),
        sa.CheckConstraint(
            "status IN ('open','partially_paid','paid')",
            name="ck_open_item_status",
        ),
    )
    op.create_index("idx_open_items_customer", "customer_open_items", ["customer_id"])
    op.create_index("idx_open_items_so", "customer_open_items", ["so_id"])
    op.create_index(
        "idx_open_items_open",
        "customer_open_items",
        ["customer_id", "status"],
        postgresql_where=sa.text("status != 'paid'"),
    )


def downgrade() -> None:
    op.drop_table("customer_open_items")
    op.drop_table("customer_credit_limits")
