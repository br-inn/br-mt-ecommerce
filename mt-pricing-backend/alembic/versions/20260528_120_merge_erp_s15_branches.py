"""merge_erp_s15_branches — consolida heads paralelos EP-ERP-05/06.

Revision ID: 20260528_120
Revises: 20260526_110, 20260527_118
Create Date: 2026-05-28
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "20260528_120"
down_revision: tuple[str, ...] = ("20260526_110", "20260527_118")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
