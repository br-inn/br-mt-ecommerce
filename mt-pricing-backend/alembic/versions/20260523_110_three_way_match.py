"""Three-way match: vendor_invoices + invoice_tolerances (US-ERP-03-04).

Revision ID: 20260523_110
Revises: 20260517_109
Create Date: 2026-05-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision = "20260523_110"
down_revision = "20260517_109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # vendor_invoices
    # ------------------------------------------------------------------
    op.create_table(
        "vendor_invoices",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("invoice_number", sa.Text(), nullable=False),
        sa.Column("vendor_id", sa.Text(), nullable=False),
        sa.Column(
            "po_id",
            sa.UUID(),
            sa.ForeignKey("purchase_orders.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "gr_id",
            sa.UUID(),
            sa.ForeignKey("goods_receipts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'AED'")),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'pending'"),
        ),
        sa.Column("payment_block", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("match_details", JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_vendor_invoices"),
        sa.UniqueConstraint("invoice_number", name="uq_vendor_invoices_number"),
        sa.CheckConstraint(
            "status IN ('pending','matched','tolerance_ok','blocked','approved','paid')",
            name="ck_vi_status",
        ),
        sa.CheckConstraint("total_amount >= 0", name="ck_vi_amount_nonneg"),
    )
    op.create_index("idx_vi_po", "vendor_invoices", ["po_id"])
    op.create_index("idx_vi_vendor_status", "vendor_invoices", ["vendor_id", "status"])
    op.create_index(
        "idx_vi_payment_block",
        "vendor_invoices",
        ["payment_block"],
        postgresql_where=sa.text("payment_block = true"),
    )

    # ------------------------------------------------------------------
    # invoice_tolerances
    # ------------------------------------------------------------------
    op.create_table(
        "invoice_tolerances",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "document_type", sa.Text(), nullable=False, server_default=sa.text("'vendor_invoice'")
        ),
        sa.Column("vendor_category", sa.Text(), nullable=True),
        sa.Column("tolerance_key", sa.Text(), nullable=False),
        sa.Column("absolute_limit", sa.Numeric(18, 4), nullable=True),
        sa.Column("pct_limit", sa.Numeric(7, 4), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'AED'")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_tolerances"),
        sa.UniqueConstraint("tolerance_key", name="uq_invoice_tolerances_key"),
    )
    op.create_index(
        "idx_it_active",
        "invoice_tolerances",
        ["tolerance_key", "is_active"],
        postgresql_where=sa.text("is_active = true"),
    )


def downgrade() -> None:
    op.drop_table("invoice_tolerances")
    op.drop_table("vendor_invoices")
