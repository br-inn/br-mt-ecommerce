"""EP-ERP-06 US-ERP-06-08 — FX Revaluation + Journal Entry SoD Controls.

Revision ID: 20260527_117
Revises: 20260527_116
Create Date: 2026-05-27

Tables: journal_entry_controls
Note: FX revaluation logic is in the API/Celery layer (no new tables).
      SoD constraint enforced at application layer + this audit table.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260527_117"
down_revision = "20260527_116"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # journal_entry_controls — SoD segregation of duties
    # -------------------------------------------------------------------------
    op.create_table(
        "journal_entry_controls",
        sa.Column("id", postgresql.UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("control_type", sa.Text(), nullable=False),
        sa.Column("gl_account_code", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.Date(), server_default=sa.text("CURRENT_DATE"), nullable=False),
        sa.Column("effective_to", sa.Date(), nullable=True),
        sa.CheckConstraint(
            "control_type IN ('PREPARER','REVIEWER','APPROVER')",
            name="ck_je_controls_type",
        ),
    )
    op.create_index("ix_je_controls_user", "journal_entry_controls", ["user_id"])
    op.create_index("ix_je_controls_type", "journal_entry_controls", ["control_type"])


def downgrade() -> None:
    op.drop_index("ix_je_controls_type", table_name="journal_entry_controls")
    op.drop_index("ix_je_controls_user", table_name="journal_entry_controls")
    op.drop_table("journal_entry_controls")
