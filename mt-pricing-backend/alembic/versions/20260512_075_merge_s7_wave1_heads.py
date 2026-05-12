"""Merge S7 Wave 1 heads: 072 + 073 + 074 → 075.

Las migraciones 072 (exception_rules versioning), 073 (price_reference_excel)
y 074 (match_candidates labels) fueron generadas en paralelo con el mismo
down_revision "20260512_071". Esta migración de merge las une en un único head
para permitir `alembic upgrade head`.

Revision ID: 20260512_075
Revises: 20260512_072, 20260512_073, 20260512_074
Create Date: 2026-05-12
"""

from __future__ import annotations

from alembic import op  # noqa: F401

revision: str = "20260512_075"
down_revision: tuple[str, ...] = ("20260512_072", "20260512_073", "20260512_074")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
