"""Merge 076 (dr_drills) + 077 (performance_indexes) → 078.

Revision ID: 20260512_078
Revises: 20260512_076, 20260512_077
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op

revision: str = "20260512_078"
down_revision: tuple[str, ...] = ("20260512_076", "20260512_077")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
