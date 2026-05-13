"""EP-ERP-06 US-ERP-06-09 — CO-PA + Cash Flow + Budget vs Actual.

Revision ID: 20260527_118
Revises: 20260527_117
Create Date: 2026-05-27

Tables: budgets
Note: CO-PA and Cash Flow are query-only APIs over financial_entries.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260527_118"
down_revision = "20260527_117"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # budgets
    # -------------------------------------------------------------------------
    op.create_table(
        "budgets",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("period_num", sa.Integer(), nullable=False),
        sa.Column("gl_account_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("gl_accounts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("profit_center_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("profit_centers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("budget_amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), server_default="AED", nullable=False),
        sa.UniqueConstraint(
            "fiscal_year", "period_num", "gl_account_id", "profit_center_id",
            name="uq_budgets_fy_period_account_pc",
        ),
    )
    op.create_index("ix_budgets_fy_period", "budgets", ["fiscal_year", "period_num"])
    op.create_index("ix_budgets_account", "budgets", ["gl_account_id"])


def downgrade() -> None:
    op.drop_index("ix_budgets_account", table_name="budgets")
    op.drop_index("ix_budgets_fy_period", table_name="budgets")
    op.drop_table("budgets")
