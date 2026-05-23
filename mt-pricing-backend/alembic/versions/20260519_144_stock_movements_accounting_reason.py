"""stock_movements_accounting_reason — accounting_document_id + reason_code columns + SCRAP seed.

US-ERP-02-01 extension:
- ADD COLUMN accounting_document_id UUID to stock_movements (nullable, no FK — avoids
  circular dep with journal_entries.id)
- ADD COLUMN reason_code TEXT to stock_movements (nullable)
- ADD COLUMN reason_code TEXT to stock_movement_types (nullable)
- Seed SCRAP movement type

Revision ID: 20260519_144
Revises: fd60e2069e3c
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260519_144"
down_revision: str | None = "fd60e2069e3c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # stock_movements — accounting_document_id (no FK to avoid circular dep)
    # ------------------------------------------------------------------
    op.add_column(
        "stock_movements",
        sa.Column(
            "accounting_document_id",
            sa.UUID(),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # stock_movements — reason_code
    # ------------------------------------------------------------------
    op.add_column(
        "stock_movements",
        sa.Column("reason_code", sa.Text(), nullable=True),
    )

    # ------------------------------------------------------------------
    # stock_movement_types — reason_code
    # ------------------------------------------------------------------
    op.add_column(
        "stock_movement_types",
        sa.Column("reason_code", sa.Text(), nullable=True),
    )

    # ------------------------------------------------------------------
    # Seed: SCRAP movement type
    # ------------------------------------------------------------------
    op.execute(
        sa.text("""
        INSERT INTO stock_movement_types
            (code, name, direction, posts_accounting, reason_code)
        VALUES
            ('SCRAP', 'Scrapping / Write-off', 'OUT', true, 'SCRAP')
        ON CONFLICT (code) DO NOTHING
    """)
    )


def downgrade() -> None:
    op.execute(sa.text("DELETE FROM stock_movement_types WHERE code = 'SCRAP'"))
    op.drop_column("stock_movement_types", "reason_code")
    op.drop_column("stock_movements", "reason_code")
    op.drop_column("stock_movements", "accounting_document_id")
