"""EP-ERP-06 US-ERP-06-03 — Universal Journal (financial_entries).

Revision ID: 20260527_112
Revises: 20260527_111
Create Date: 2026-05-27

Tables: financial_entries
Triggers: validate_balanced_entry (para entry_type != MANUAL)
Indexes: period+fy, account+date, source_module+doc_id, journal_date
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260527_112"
down_revision = "20260527_111"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # financial_entries — Universal Journal
    # NOTE: Esta tabla es DIFERENTE de journal_entries (inventario/stock movements)
    # -------------------------------------------------------------------------
    op.create_table(
        "financial_entries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("entry_number", sa.Text(), nullable=False),
        sa.Column("journal_date", sa.Date(), nullable=False),
        sa.Column("posting_period", sa.Integer(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("entry_type", sa.Text(), nullable=False),
        sa.Column("source_module", sa.Text(), nullable=True),
        sa.Column("source_document", sa.Text(), nullable=True),
        sa.Column("source_document_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "gl_account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gl_accounts.id"),
            nullable=False,
        ),
        sa.Column(
            "cost_center_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cost_centers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "profit_center_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("profit_centers.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("debit_amount", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("credit_amount", sa.Numeric(18, 4), server_default="0", nullable=False),
        sa.Column("currency_code", sa.CHAR(3), server_default="AED", nullable=False),
        sa.Column("amount_local", sa.Numeric(18, 4), nullable=True),
        sa.Column("fx_rate", sa.Numeric(14, 6), server_default="1", nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("reference", sa.Text(), nullable=True),
        sa.Column(
            "preparer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "reviewer_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "approver_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_reversed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "reversal_entry_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_entries.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "entry_type IN ('MANUAL','SYSTEM','REVERSAL','ACCRUAL','FX_REVAL')",
            name="ck_financial_entries_entry_type",
        ),
        sa.CheckConstraint(
            "source_module IN ('billing','procurement','inventory','sales','finance','fx') OR source_module IS NULL",
            name="ck_financial_entries_source_module",
        ),
        sa.CheckConstraint("debit_amount >= 0", name="ck_financial_entries_debit_pos"),
        sa.CheckConstraint("credit_amount >= 0", name="ck_financial_entries_credit_pos"),
        sa.CheckConstraint(
            "debit_amount > 0 OR credit_amount > 0", name="ck_financial_entries_nonzero"
        ),
        sa.UniqueConstraint("entry_number", name="uq_financial_entries_number"),
    )

    # Indexes
    op.create_index("ix_fe_period_fy", "financial_entries", ["posting_period", "fiscal_year"])
    op.create_index("ix_fe_account_date", "financial_entries", ["gl_account_id", "journal_date"])
    op.create_index("ix_fe_source", "financial_entries", ["source_module", "source_document_id"])
    op.create_index("ix_fe_journal_date", "financial_entries", ["journal_date"])

    # -------------------------------------------------------------------------
    # Function + trigger: validate balanced entries for SYSTEM/REVERSAL/ACCRUAL/FX_REVAL
    # -------------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION fn_validate_balanced_entry()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        DECLARE
            v_debit  NUMERIC;
            v_credit NUMERIC;
        BEGIN
            -- Solo validar para asientos no-manuales con source_document
            IF NEW.entry_type = 'MANUAL' OR NEW.source_document IS NULL THEN
                RETURN NEW;
            END IF;

            SELECT
                COALESCE(SUM(debit_amount), 0),
                COALESCE(SUM(credit_amount), 0)
            INTO v_debit, v_credit
            FROM financial_entries
            WHERE source_document = NEW.source_document
              AND entry_type != 'MANUAL';

            -- Incluir la fila que se está insertando
            v_debit  := v_debit  + NEW.debit_amount;
            v_credit := v_credit + NEW.credit_amount;

            -- Sólo forzar balance si el documento ya tiene múltiples líneas
            -- (permitir inserción de primera línea sin error)
            IF v_debit != v_credit AND v_debit > 0 AND v_credit > 0 THEN
                RAISE EXCEPTION
                    'Asiento desequilibrado para source_document=%: debe=% haber=%',
                    NEW.source_document, v_debit, v_credit;
            END IF;

            RETURN NEW;
        END;
        $$;
    """)

    op.execute("""
        CREATE TRIGGER trg_validate_balanced_entry
        BEFORE INSERT ON financial_entries
        FOR EACH ROW
        EXECUTE FUNCTION fn_validate_balanced_entry();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_validate_balanced_entry ON financial_entries")
    op.execute("DROP FUNCTION IF EXISTS fn_validate_balanced_entry()")
    op.drop_index("ix_fe_journal_date", table_name="financial_entries")
    op.drop_index("ix_fe_source", table_name="financial_entries")
    op.drop_index("ix_fe_account_date", table_name="financial_entries")
    op.drop_index("ix_fe_period_fy", table_name="financial_entries")
    op.drop_table("financial_entries")
