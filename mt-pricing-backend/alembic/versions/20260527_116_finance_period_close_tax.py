"""EP-ERP-06 US-ERP-06-07 — Period Close Checklist + UAE CIT Provisioning.

Revision ID: 20260527_116
Revises: 20260527_115
Create Date: 2026-05-27

Tables: period_close_checklists, tax_provisions
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260527_116"
down_revision = "20260527_115"
branch_labels = None
depends_on = None

_DEFAULT_CHECKLIST = (
    '["Reconcile AR", "Reconcile AP", "Post accruals", "Run depreciation", '
    '"FX revaluation", "Close subledgers", "Review variances", "CIT provision", "Lock period"]'
)


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # period_close_checklists
    # -------------------------------------------------------------------------
    op.create_table(
        "period_close_checklists",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("period_num", sa.Integer(), nullable=True),
        sa.Column(
            "checklist_items",
            postgresql.JSONB(),
            server_default=sa.text(f"'{_DEFAULT_CHECKLIST}'::jsonb"),
            nullable=False,
        ),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("started_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "completed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint(
            "status IN ('open','in_progress','closed')",
            name="ck_period_close_checklists_status",
        ),
        sa.UniqueConstraint("fiscal_year", "period_num", name="uq_period_close_fy_period"),
    )
    op.create_index(
        "ix_period_close_fy_period", "period_close_checklists", ["fiscal_year", "period_num"]
    )

    # -------------------------------------------------------------------------
    # tax_provisions
    # -------------------------------------------------------------------------
    op.create_table(
        "tax_provisions",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("provision_type", sa.Text(), nullable=True),
        sa.Column("fiscal_year", sa.Integer(), nullable=True),
        sa.Column("period_num", sa.Integer(), nullable=True),
        sa.Column("taxable_base", sa.Numeric(18, 4), nullable=True),
        sa.Column("tax_rate", sa.Numeric(7, 4), nullable=True),
        sa.Column("provision_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("status", sa.Text(), server_default="draft", nullable=False),
        sa.Column("gl_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "provision_type IN ('VAT','CIT','WHT') OR provision_type IS NULL",
            name="ck_tax_provisions_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','posted','filed')",
            name="ck_tax_provisions_status",
        ),
    )
    op.create_index("ix_tax_provisions_fy_period", "tax_provisions", ["fiscal_year", "period_num"])
    op.create_index("ix_tax_provisions_type", "tax_provisions", ["provision_type"])


def downgrade() -> None:
    op.drop_index("ix_tax_provisions_type", table_name="tax_provisions")
    op.drop_index("ix_tax_provisions_fy_period", table_name="tax_provisions")
    op.drop_table("tax_provisions")
    op.drop_index("ix_period_close_fy_period", table_name="period_close_checklists")
    op.drop_table("period_close_checklists")
