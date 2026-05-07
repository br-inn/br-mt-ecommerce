"""escalation + notifications — US-1B-02-08 (Sprint 6).

Cambios:
- Tabla ``notifications``:
    * id UUID PK
    * recipient_user_id UUID NOT NULL FK→users(id) (CASCADE)
    * kind TEXT NOT NULL — e.g. 'price.escalated', 'price.digest', 'system.warning'
    * payload JSONB NOT NULL DEFAULT '{}'
    * seen_at TIMESTAMPTZ NULL
    * created_at TIMESTAMPTZ DEFAULT now()
    * (recipient, created_at DESC) index for inbox queries
- Columnas ``prices``:
    * escalated BOOLEAN NOT NULL DEFAULT false
    * escalated_at TIMESTAMPTZ NULL
    * partial index on `escalated=true` for the worker scan
- Columna ``users``:
    * delegate_user_id UUID NULL FK→users(id) (SET NULL) — auto-escalate target

Slot 029.

Revision ID: 20260507_029
Revises: 20260507_028
Create Date: 2026-05-07
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID

revision: str = "20260507_029"
down_revision: str | None = "20260507_028"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column(
            "id",
            PgUUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "recipient_user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("kind", sa.Text, nullable=False),
        sa.Column(
            "payload",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "idx_notifications_inbox",
        "notifications",
        ["recipient_user_id", sa.text("created_at DESC")],
    )
    op.create_index("idx_notifications_kind", "notifications", ["kind"])

    op.add_column(
        "prices",
        sa.Column(
            "escalated",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("false"),
        ),
    )
    op.add_column(
        "prices",
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        CREATE INDEX idx_prices_escalated
            ON prices (escalated_at)
            WHERE escalated = true;
        """
    )

    op.add_column(
        "users",
        sa.Column(
            "delegate_user_id",
            PgUUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index(
        "idx_users_delegate", "users", ["delegate_user_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("idx_users_delegate", table_name="users")
    op.drop_column("users", "delegate_user_id")

    op.execute("DROP INDEX IF EXISTS idx_prices_escalated")
    op.drop_column("prices", "escalated_at")
    op.drop_column("prices", "escalated")

    op.drop_index("idx_notifications_kind", table_name="notifications")
    op.drop_index("idx_notifications_inbox", table_name="notifications")
    op.drop_table("notifications")
