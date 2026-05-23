"""return_deliveries — tabla de recepción física de devoluciones (VEN-18, US-ERP-04-05).

Revision ID: 20260519_151
Revises: 20260519_150
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "20260519_151"
down_revision: str | None = "20260519_150"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "return_deliveries",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "rma_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("rma_headers.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("received_date", sa.Date(), nullable=False),
        sa.Column(
            "received_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("idx_return_delivery_rma", "return_deliveries", ["rma_id"])


def downgrade() -> None:
    op.drop_index("idx_return_delivery_rma", table_name="return_deliveries")
    op.drop_table("return_deliveries")
