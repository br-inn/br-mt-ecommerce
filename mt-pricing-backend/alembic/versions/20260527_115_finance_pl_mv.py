"""EP-ERP-06 US-ERP-06-06 — P&L materialized view.

Revision ID: 20260527_115
Revises: 20260527_114
Create Date: 2026-05-27

Views: mv_pl_summary (materialized view for P&L + Balance Sheet queries)
"""

from __future__ import annotations

from alembic import op

revision = "20260527_115"
down_revision = "20260527_114"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE MATERIALIZED VIEW mv_pl_summary AS
        SELECT
            fe.fiscal_year,
            fe.posting_period,
            fe.gl_account_id,
            a.account_code,
            a.account_name,
            a.account_type,
            SUM(fe.debit_amount)                   AS total_debit,
            SUM(fe.credit_amount)                  AS total_credit,
            SUM(fe.credit_amount - fe.debit_amount) AS net_amount
        FROM financial_entries fe
        JOIN gl_accounts a ON fe.gl_account_id = a.id
        GROUP BY fe.fiscal_year, fe.posting_period, fe.gl_account_id,
                 a.account_code, a.account_name, a.account_type
        WITH DATA
    """)

    op.execute("""
        CREATE UNIQUE INDEX ix_mv_pl_fy_period_account
        ON mv_pl_summary (fiscal_year, posting_period, gl_account_id)
    """)

    op.execute("""
        CREATE INDEX ix_mv_pl_account_type
        ON mv_pl_summary (account_type, fiscal_year, posting_period)
    """)


def downgrade() -> None:
    op.execute("DROP MATERIALIZED VIEW IF EXISTS mv_pl_summary")
