"""merge_erp_s14_branches — consolida heads paralelos EP-ERP-02/03/04.

Revision ID: 20260525_115
Revises: 20260522_110, 20260523_111, 20260524_114
Create Date: 2026-05-25
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260525_115"
down_revision: tuple[str, ...] = ("20260522_110", "20260523_111", "20260524_114")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
