"""Tabla dr_drills — registro de ejercicios DR.

Revision ID: 20260512_076
Revises: 20260512_075
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_076"
down_revision: str = "20260512_075"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "dr_drills",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("drill_type", sa.String(50), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=False),
        sa.Column("executed_date", sa.Date(), nullable=True),
        sa.Column("outcome", sa.String(20), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=True),
        sa.Column("findings", sa.Text(), nullable=True),
        sa.Column("runbook_ref", sa.String(100), nullable=True),
        sa.Column(
            "conducted_by_user_id",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name="pk_dr_drills"),
        sa.CheckConstraint(
            "outcome IN ('pass', 'fail', 'partial')",
            name="ck_dr_drills_outcome",
        ),
    )
    op.create_index("idx_dr_drills_scheduled_date", "dr_drills", ["scheduled_date"])
    op.create_index("idx_dr_drills_outcome", "dr_drills", ["outcome"])


def downgrade() -> None:
    op.drop_index("idx_dr_drills_outcome", table_name="dr_drills")
    op.drop_index("idx_dr_drills_scheduled_date", table_name="dr_drills")
    op.drop_table("dr_drills")
