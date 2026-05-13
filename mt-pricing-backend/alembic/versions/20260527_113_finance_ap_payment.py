"""EP-ERP-06 US-ERP-06-04 — AP Aging + Payment Run.

Revision ID: 20260527_113
Revises: 20260527_112
Create Date: 2026-05-27

Tables: vendor_open_items, payment_runs, payment_run_items
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260527_113"
down_revision = "20260527_112"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # vendor_open_items
    # -------------------------------------------------------------------------
    op.create_table(
        "vendor_open_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("vendor_id", sa.Text(), nullable=False),
        sa.Column("po_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("purchase_orders.id", ondelete="SET NULL"), nullable=True),
        sa.Column("invoice_ref", sa.Text(), nullable=True),
        sa.Column("document_type", sa.Text(), server_default="vendor_invoice", nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), server_default="AED", nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("payment_block", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "document_type IN ('vendor_invoice','debit_memo','credit_note')",
            name="ck_vendor_open_items_doc_type",
        ),
        sa.CheckConstraint(
            "status IN ('open','partially_paid','paid','blocked')",
            name="ck_vendor_open_items_status",
        ),
    )
    op.create_index("ix_vendor_open_items_vendor", "vendor_open_items", ["vendor_id"])
    op.create_index("ix_vendor_open_items_due", "vendor_open_items", ["due_date"])
    op.create_index("ix_vendor_open_items_status", "vendor_open_items", ["status"])

    # -------------------------------------------------------------------------
    # payment_runs
    # -------------------------------------------------------------------------
    op.create_table(
        "payment_runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("run_number", sa.Text(), nullable=False),
        sa.Column("run_date", sa.Date(), nullable=False),
        sa.Column("payment_method", sa.Text(), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.CHAR(3), server_default="AED", nullable=False),
        sa.Column("status", sa.Text(), server_default="proposed", nullable=False),
        sa.Column("created_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "payment_method IN ('bank_transfer','check','wire') OR payment_method IS NULL",
            name="ck_payment_runs_method",
        ),
        sa.CheckConstraint(
            "status IN ('proposed','approved','executed','cancelled')",
            name="ck_payment_runs_status",
        ),
        sa.UniqueConstraint("run_number", name="uq_payment_runs_number"),
    )
    op.create_index("ix_payment_runs_date", "payment_runs", ["run_date"])
    op.create_index("ix_payment_runs_status", "payment_runs", ["status"])

    # -------------------------------------------------------------------------
    # payment_run_items
    # -------------------------------------------------------------------------
    op.create_table(
        "payment_run_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("run_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("payment_runs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("open_item_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("vendor_open_items.id", ondelete="CASCADE"), nullable=False),
        sa.Column("payment_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("discount_taken", sa.Numeric(18, 4), server_default="0", nullable=False),
    )
    op.create_index("ix_payment_run_items_run", "payment_run_items", ["run_id"])


def downgrade() -> None:
    op.drop_index("ix_payment_run_items_run", table_name="payment_run_items")
    op.drop_table("payment_run_items")
    op.drop_index("ix_payment_runs_status", table_name="payment_runs")
    op.drop_index("ix_payment_runs_date", table_name="payment_runs")
    op.drop_table("payment_runs")
    op.drop_index("ix_vendor_open_items_status", table_name="vendor_open_items")
    op.drop_index("ix_vendor_open_items_due", table_name="vendor_open_items")
    op.drop_index("ix_vendor_open_items_vendor", table_name="vendor_open_items")
    op.drop_table("vendor_open_items")
