"""source_list_warehouse_id — ADD COLUMN warehouse_id UUID to source_list.

US-ERP-03-05 extension: links approved vendor entries in the source list to a
specific warehouse, enabling warehouse-scoped vendor-of-record rules.

Revision ID: 20260519_147
Revises: 20260519_146
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "20260519_147"
down_revision: str | None = "20260519_146"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "source_list",
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )
    op.create_index("idx_sl_warehouse", "source_list", ["warehouse_id"])


def downgrade() -> None:
    op.drop_index("idx_sl_warehouse", table_name="source_list")
    op.drop_column("source_list", "warehouse_id")
