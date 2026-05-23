"""cycle_counts — execution records for cycle count schedules (US-ERP-02-07).

Revision ID: 20260602_137
Revises: 20260602_136
Create Date: 2026-06-02

Tablas:
- ``cycle_counts`` — registros de ejecución de conteos cíclicos por schedule × SKU × almacén.
  Almacena qty contada, qty sistema (snapshot) y varianza calculada.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260602_137"
down_revision = "20260602_136"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # cycle_counts — registros de conteo cíclico ejecutado
    # ------------------------------------------------------------------
    op.create_table(
        "cycle_counts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column(
            "schedule_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("cycle_count_schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "location_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouse_locations.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "warehouse_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("warehouses.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "scheduled_date",
            sa.Date(),
            nullable=False,
        ),
        # nullable until counted
        sa.Column("counted_qty", sa.Numeric(15, 3), nullable=True),
        # snapshot of InventoryPosition.qty_on_hand at count time
        sa.Column("system_qty", sa.Numeric(15, 3), nullable=True),
        # computed as counted_qty - system_qty (regular column, not GENERATED ALWAYS)
        sa.Column("variance", sa.Numeric(15, 3), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'scheduled'"),
        ),
        sa.Column("counted_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("approved_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.CheckConstraint(
            "status IN ('scheduled','in_progress','pending_approval','approved','rejected')",
            name="ck_cycle_counts_status",
        ),
    )

    op.create_index(
        "ix_cc_schedule",
        "cycle_counts",
        ["schedule_id"],
    )
    op.create_index(
        "ix_cc_sku_wh",
        "cycle_counts",
        ["product_sku", "warehouse_id", "scheduled_date"],
    )

    # ------------------------------------------------------------------
    # updated_at auto-refresh trigger
    # ------------------------------------------------------------------
    op.execute("""
        CREATE OR REPLACE FUNCTION cycle_counts_updated_at()
        RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$
    """)

    op.execute("""
        CREATE TRIGGER trg_cycle_counts_updated_at
        BEFORE UPDATE ON cycle_counts
        FOR EACH ROW EXECUTE FUNCTION cycle_counts_updated_at()
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_cycle_counts_updated_at ON cycle_counts")
    op.execute("DROP FUNCTION IF EXISTS cycle_counts_updated_at()")
    op.drop_index("ix_cc_sku_wh", table_name="cycle_counts")
    op.drop_index("ix_cc_schedule", table_name="cycle_counts")
    op.drop_table("cycle_counts")
