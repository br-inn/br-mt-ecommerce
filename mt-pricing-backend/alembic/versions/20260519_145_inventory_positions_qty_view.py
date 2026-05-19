"""inventory_positions_qty_view — CREATE VIEW inventory_positions_5d (pivoted 5D).

SQL VIEW (no new table) that presents inventory_positions in a pivoted format
grouping the 4 stock_type values into named quantity columns.

stock_type values come from mig 20260515_106:
  unrestricted | quality_inspection | restricted | in_transit

Revision ID: 20260519_145
Revises: 20260519_144
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "20260519_145"
down_revision: str | None = "20260519_144"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE VIEW inventory_positions_5d AS
        SELECT
            sku,
            warehouse_id,
            SUM(CASE WHEN stock_type = 'unrestricted'        THEN qty_on_hand ELSE 0 END) AS qty_on_hand,
            SUM(CASE WHEN stock_type = 'restricted'          THEN qty_on_hand ELSE 0 END) AS qty_reserved,
            SUM(CASE WHEN stock_type = 'in_transit'          THEN qty_on_hand ELSE 0 END) AS qty_in_transit,
            SUM(CASE WHEN stock_type = 'quality_inspection'  THEN qty_on_hand ELSE 0 END) AS qty_inspection,
            0::numeric                                                                      AS qty_blocked
        FROM inventory_positions
        GROUP BY sku, warehouse_id
    """)


def downgrade() -> None:
    op.execute("DROP VIEW IF EXISTS inventory_positions_5d")
