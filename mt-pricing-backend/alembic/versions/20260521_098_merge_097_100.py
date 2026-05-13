"""merge_097_100 — merge heads 097 (M1 releases/uom/gtin) y 100 (demo seed).

Slot 098.
"""

from __future__ import annotations

from collections.abc import Sequence

revision: str = "098"
down_revision: tuple[str, str] = ("097", "20260513_100")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
