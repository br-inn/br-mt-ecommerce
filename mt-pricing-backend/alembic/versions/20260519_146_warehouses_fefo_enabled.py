"""warehouses_fefo_enabled — ADD COLUMN fefo_enabled BOOLEAN NOT NULL DEFAULT true.

US-ERP-02-05 FEFO: each warehouse now carries an explicit opt-in flag so the
picking engine can selectively apply FEFO logic per physical location.

Revision ID: 20260519_146
Revises: 20260519_145
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260519_146"
down_revision: str | None = "20260519_145"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "warehouses",
        sa.Column(
            "fefo_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )


def downgrade() -> None:
    op.drop_column("warehouses", "fefo_enabled")
