"""Billing & Facturación — tablas core + dunning + e-invoice + payment promises (EP-ERP-05).

Revision ID: 20260526_110
Revises: 20260525_115
Create Date: 2026-05-26
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260526_110"
down_revision: str = "20260525_115"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # invoices
    # -------------------------------------------------------------------------
    op.create_table(
        "invoices",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invoice_number", sa.Text(), nullable=False),
        sa.Column("invoice_type", sa.Text(), server_default=sa.text("'STANDARD'"), nullable=False),
        sa.Column("delivery_id", sa.UUID(), nullable=True),
        sa.Column("so_id", sa.UUID(), nullable=True),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column("invoice_date", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(18, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("currency", sa.CHAR(3), server_default=sa.text("'AED'"), nullable=False),
        sa.Column("status", sa.Text(), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("accounting_document_id", sa.UUID(), nullable=True),
        sa.Column("payment_terms", sa.Text(), server_default=sa.text("'NET30'"), nullable=False),
        sa.Column("e_invoice_status", sa.Text(), server_default=sa.text("'not_required'"), nullable=False),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invoice_number"),
        sa.CheckConstraint(
            "invoice_type IN ('STANDARD','CREDIT_MEMO','DEBIT_MEMO','PROFORMA','INTERCOMPANY')",
            name="ck_invoice_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','posted','cancelled','reversed')",
            name="ck_invoice_status",
        ),
        sa.CheckConstraint(
            "e_invoice_status IN ('not_required','pending','compliant','rejected')",
            name="ck_invoice_e_invoice_status",
        ),
        sa.ForeignKeyConstraint(["delivery_id"], ["outbound_deliveries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["so_id"], ["sales_orders.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_invoice_customer_id", "invoices", ["customer_id"])
    op.create_index("idx_invoice_status", "invoices", ["status"])
    op.create_index("idx_invoice_so_id", "invoices", ["so_id"])
    op.create_index("idx_invoice_delivery_id", "invoices", ["delivery_id"])
    op.create_index("idx_invoice_due_date", "invoices", ["due_date"])

    # -------------------------------------------------------------------------
    # invoice_lines
    # -------------------------------------------------------------------------
    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("so_line_id", sa.UUID(), nullable=True),
        sa.Column("product_sku", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=False),
        sa.Column("discount_pct", sa.Numeric(5, 2), server_default=sa.text("0"), nullable=False),
        sa.Column("tax_rate", sa.Numeric(5, 2), server_default=sa.text("5"), nullable=False),
        sa.Column("line_total", sa.Numeric(18, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(18, 4), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["so_line_id"], ["sales_order_lines.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["product_sku"], ["products.sku"], ondelete="RESTRICT"),
    )
    op.create_index("idx_invoice_line_invoice_id", "invoice_lines", ["invoice_id"])
    op.create_index("idx_invoice_line_sku", "invoice_lines", ["product_sku"])

    # -------------------------------------------------------------------------
    # dunning_levels
    # -------------------------------------------------------------------------
    op.create_table(
        "dunning_levels",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("days_overdue", sa.Integer(), nullable=False),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("fee_amount", sa.Numeric(18, 4), server_default=sa.text("0"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("level"),
        sa.CheckConstraint(
            "action IN ('reminder','warning','final_notice','legal')",
            name="ck_dunning_level_action",
        ),
    )

    # Seed dunning levels
    op.execute(
        """
        INSERT INTO dunning_levels (id, level, days_overdue, action, fee_amount, is_active)
        VALUES
          (gen_random_uuid(), 1, 15, 'reminder',     0,    true),
          (gen_random_uuid(), 2, 30, 'warning',      0,    true),
          (gen_random_uuid(), 3, 45, 'final_notice', 0,    true),
          (gen_random_uuid(), 4, 60, 'legal',        0,    true)
        ON CONFLICT (level) DO NOTHING
        """
    )

    # -------------------------------------------------------------------------
    # dunning_history
    # -------------------------------------------------------------------------
    op.create_table(
        "dunning_history",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column("dunning_level", sa.Integer(), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_dunning_history_invoice_id", "dunning_history", ["invoice_id"])
    op.create_index("idx_dunning_history_customer_id", "dunning_history", ["customer_id"])

    # -------------------------------------------------------------------------
    # e_invoice_submissions
    # -------------------------------------------------------------------------
    op.create_table(
        "e_invoice_submissions",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("standard", sa.Text(), nullable=False),
        sa.Column("submission_ref", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("response_code", sa.Text(), nullable=True),
        sa.Column("response_message", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("xml_payload", sa.Text(), nullable=True),
        sa.Column("qr_code", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "standard IN ('CFDI_4.0','ZATCA_PHASE2','UBL_2.1','PEPPOL')",
            name="ck_e_invoice_standard",
        ),
        sa.CheckConstraint(
            "status IN ('pending','submitted','accepted','rejected','cancelled')",
            name="ck_e_invoice_status",
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
    )
    op.create_index("idx_e_invoice_invoice_id", "e_invoice_submissions", ["invoice_id"])
    op.create_index("idx_e_invoice_status", "e_invoice_submissions", ["status"])

    # -------------------------------------------------------------------------
    # payment_promises
    # -------------------------------------------------------------------------
    op.create_table(
        "payment_promises",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invoice_id", sa.UUID(), nullable=False),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column("promised_date", sa.Date(), nullable=False),
        sa.Column("promised_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.Text(), server_default=sa.text("'active'"), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint(
            "status IN ('active','kept','broken','cancelled')",
            name="ck_payment_promise_status",
        ),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index("idx_payment_promise_invoice_id", "payment_promises", ["invoice_id"])
    op.create_index("idx_payment_promise_customer_id", "payment_promises", ["customer_id"])
    op.create_index("idx_payment_promise_promised_date", "payment_promises", ["promised_date"])

    # -------------------------------------------------------------------------
    # job_definitions seeds — billing tasks
    # -------------------------------------------------------------------------
    op.execute(
        """
        INSERT INTO job_definitions (id, name, task_name, cron_expression, queue, owner, is_active, description)
        VALUES
          (gen_random_uuid(), 'billing_dunning_check',
           'mt.billing.run_dunning_check',
           '0 8 * * *', 'default', 'business', true,
           'EP-ERP-05-03: Evalúa invoices en mora y registra historial de dunning'),
          (gen_random_uuid(), 'billing_check_unposted_deliveries',
           'mt.billing.check_unposted_deliveries',
           '0 */4 * * *', 'default', 'business', true,
           'EP-ERP-05-06: Alerta deliveries shipped sin invoice en 24h'),
          (gen_random_uuid(), 'billing_mark_broken_promises',
           'mt.billing.mark_broken_promises',
           '0 8 * * *', 'default', 'business', true,
           'EP-ERP-05-05: Marca promesas de pago vencidas como broken')
        ON CONFLICT (name) DO NOTHING
        """
    )


def downgrade() -> None:
    # Remove job definitions seeds
    op.execute(
        """
        DELETE FROM job_definitions
        WHERE name IN ('billing_dunning_check','billing_check_unposted_deliveries','billing_mark_broken_promises')
        """
    )

    op.drop_index("idx_payment_promise_promised_date", table_name="payment_promises")
    op.drop_index("idx_payment_promise_customer_id", table_name="payment_promises")
    op.drop_index("idx_payment_promise_invoice_id", table_name="payment_promises")
    op.drop_table("payment_promises")

    op.drop_index("idx_e_invoice_status", table_name="e_invoice_submissions")
    op.drop_index("idx_e_invoice_invoice_id", table_name="e_invoice_submissions")
    op.drop_table("e_invoice_submissions")

    op.drop_index("idx_dunning_history_customer_id", table_name="dunning_history")
    op.drop_index("idx_dunning_history_invoice_id", table_name="dunning_history")
    op.drop_table("dunning_history")
    op.drop_table("dunning_levels")

    op.drop_index("idx_invoice_line_sku", table_name="invoice_lines")
    op.drop_index("idx_invoice_line_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")

    op.drop_index("idx_invoice_due_date", table_name="invoices")
    op.drop_index("idx_invoice_delivery_id", table_name="invoices")
    op.drop_index("idx_invoice_so_id", table_name="invoices")
    op.drop_index("idx_invoice_status", table_name="invoices")
    op.drop_index("idx_invoice_customer_id", table_name="invoices")
    op.drop_table("invoices")
