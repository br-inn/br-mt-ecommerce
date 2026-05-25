"""fix approval_decisions and approval_rules schema drift.

Alinea el esquema de BD con los modelos ORM actuales:
- approval_decisions: document_type/action TEXT→varchar, decided_at NOT NULL,
  FK approver_id auth.users→public.users con RESTRICT.
- approval_rules: document_type/category_id TEXT→varchar(64),
  approver_role TEXT→varchar(32),
  FK approver_user_id auth.users→public.users con SET NULL.

Revision ID: 20260525_156
Revises: 20260522_155
Create Date: 2026-05-25
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import text

from alembic import op

revision = "20260525_156"
down_revision = "20260522_155"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── approval_decisions ───────────────────────────────────────────────────
    op.alter_column(
        "approval_decisions",
        "document_type",
        existing_type=sa.Text(),
        type_=sa.String(64),
        existing_nullable=False,
    )
    op.alter_column(
        "approval_decisions",
        "action",
        existing_type=sa.Text(),
        type_=sa.String(16),
        existing_nullable=False,
    )
    # Backfill any NULL decided_at rows before enforcing NOT NULL.
    null_count = conn.execute(
        text("SELECT count(*) FROM approval_decisions WHERE decided_at IS NULL")
    ).scalar()
    if null_count:
        op.execute("UPDATE approval_decisions SET decided_at = now() WHERE decided_at IS NULL")
    op.alter_column(
        "approval_decisions",
        "decided_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        existing_server_default=sa.text("now()"),
    )
    # FK: auth.users → public.users (RESTRICT)
    op.drop_constraint(
        "approval_decisions_approver_id_fkey",
        "approval_decisions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "approval_decisions_approver_id_fkey",
        "approval_decisions",
        "users",
        ["approver_id"],
        ["id"],
        referent_schema="public",
        ondelete="RESTRICT",
    )

    # ── approval_rules ───────────────────────────────────────────────────────
    op.alter_column(
        "approval_rules",
        "document_type",
        existing_type=sa.Text(),
        type_=sa.String(64),
        existing_nullable=False,
    )
    op.alter_column(
        "approval_rules",
        "category_id",
        existing_type=sa.Text(),
        type_=sa.String(64),
        existing_nullable=True,
    )
    op.alter_column(
        "approval_rules",
        "approver_role",
        existing_type=sa.Text(),
        type_=sa.String(32),
        existing_nullable=True,
    )
    # is_active and created_at: DB created nullable, model requires NOT NULL.
    op.alter_column(
        "approval_rules",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=False,
        existing_server_default=sa.text("true"),
    )
    op.alter_column(
        "approval_rules",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=False,
        existing_server_default=sa.text("now()"),
    )
    # FK: auth.users → public.users (SET NULL)
    op.drop_constraint(
        "approval_rules_approver_user_id_fkey",
        "approval_rules",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "approval_rules_approver_user_id_fkey",
        "approval_rules",
        "users",
        ["approver_user_id"],
        ["id"],
        referent_schema="public",
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # ── approval_rules ───────────────────────────────────────────────────────
    op.drop_constraint(
        "approval_rules_approver_user_id_fkey",
        "approval_rules",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "approval_rules_approver_user_id_fkey",
        "approval_rules",
        "users",
        ["approver_user_id"],
        ["id"],
        referent_schema="auth",
    )
    op.alter_column(
        "approval_rules",
        "created_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "approval_rules",
        "is_active",
        existing_type=sa.Boolean(),
        nullable=True,
        existing_server_default=sa.text("true"),
    )
    op.alter_column(
        "approval_rules",
        "approver_role",
        existing_type=sa.String(32),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "approval_rules",
        "category_id",
        existing_type=sa.String(64),
        type_=sa.Text(),
        existing_nullable=True,
    )
    op.alter_column(
        "approval_rules",
        "document_type",
        existing_type=sa.String(64),
        type_=sa.Text(),
        existing_nullable=False,
    )

    # ── approval_decisions ───────────────────────────────────────────────────
    op.drop_constraint(
        "approval_decisions_approver_id_fkey",
        "approval_decisions",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "approval_decisions_approver_id_fkey",
        "approval_decisions",
        "users",
        ["approver_id"],
        ["id"],
        referent_schema="auth",
    )
    op.alter_column(
        "approval_decisions",
        "decided_at",
        existing_type=sa.DateTime(timezone=True),
        nullable=True,
        existing_server_default=sa.text("now()"),
    )
    op.alter_column(
        "approval_decisions",
        "action",
        existing_type=sa.String(16),
        type_=sa.Text(),
        existing_nullable=False,
    )
    op.alter_column(
        "approval_decisions",
        "document_type",
        existing_type=sa.String(64),
        type_=sa.Text(),
        existing_nullable=False,
    )
