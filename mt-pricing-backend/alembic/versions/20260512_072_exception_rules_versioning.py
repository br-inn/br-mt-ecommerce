"""US-1B-02-02 — versioning fields for exception_rules.

Agrega version, effective_from, effective_to, created_by a la tabla
`exception_rules` para soporte de historial y cierre automático de
la versión anterior al activar una nueva regla.

Revision ID: 20260512_072
Revises: 20260512_071
Create Date: 2026-05-12
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260512_072"
down_revision: str = "20260512_071"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "exception_rules",
        sa.Column(
            "version",
            sa.Integer(),
            nullable=False,
            server_default=sa.text("1"),
        ),
    )
    op.add_column(
        "exception_rules",
        sa.Column(
            "effective_from",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.add_column(
        "exception_rules",
        sa.Column(
            "effective_to",
            sa.DateTime(timezone=True),
            nullable=True,
        ),
    )
    op.add_column(
        "exception_rules",
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("exception_rules", "created_by")
    op.drop_column("exception_rules", "effective_to")
    op.drop_column("exception_rules", "effective_from")
    op.drop_column("exception_rules", "version")
