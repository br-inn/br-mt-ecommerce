"""EP-ERP-02 US-ERP-02-04 — warehouses, warehouse_zones, warehouse_locations + FK inventory_positions.

Jerarquía física de almacenamiento: Warehouse → Zone → Location (bin).
Materializa las FK warehouse_id y location_id que se dejaron nullable en
migraciones anteriores.

Revision ID: 20260515_108
Revises: 20260515_107
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "20260515_108"
down_revision: str = "20260515_107"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # warehouses
    # ------------------------------------------------------------------
    op.create_table(
        "warehouses",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
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
        sa.UniqueConstraint("code", name="uq_warehouse_code"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ------------------------------------------------------------------
    # warehouse_zones
    # ------------------------------------------------------------------
    op.create_table(
        "warehouse_zones",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("warehouse_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("zone_type", sa.Text(), nullable=True),
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
            "zone_type IN ('refrigerated','dry','hazardous','general') OR zone_type IS NULL",
            name="ck_zone_type",
        ),
        sa.ForeignKeyConstraint(["warehouse_id"], ["warehouses.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("warehouse_id", "code", name="uq_zone_wh_code"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_zones_warehouse", "warehouse_zones", ["warehouse_id"])

    # ------------------------------------------------------------------
    # warehouse_locations
    # ------------------------------------------------------------------
    op.create_table(
        "warehouse_locations",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("zone_id", sa.UUID(), nullable=False),
        sa.Column("bin_code", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("max_weight", sa.Numeric(10, 2), nullable=True),
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
        sa.ForeignKeyConstraint(["zone_id"], ["warehouse_zones.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("zone_id", "bin_code", name="uq_location_zone_bin"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_locations_zone", "warehouse_locations", ["zone_id"])

    # ------------------------------------------------------------------
    # FK warehouse_id y location_id en inventory_positions
    # ------------------------------------------------------------------
    op.create_foreign_key(
        "fk_inv_pos_warehouse",
        "inventory_positions",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_inv_pos_location",
        "inventory_positions",
        "warehouse_locations",
        ["location_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # FK warehouse_id en stock_movements
    op.create_foreign_key(
        "fk_sm_warehouse",
        "stock_movements",
        "warehouses",
        ["warehouse_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_sm_location",
        "stock_movements",
        "warehouse_locations",
        ["location_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_sm_location", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_sm_warehouse", "stock_movements", type_="foreignkey")
    op.drop_constraint("fk_inv_pos_location", "inventory_positions", type_="foreignkey")
    op.drop_constraint("fk_inv_pos_warehouse", "inventory_positions", type_="foreignkey")
    op.drop_table("warehouse_locations")
    op.drop_table("warehouse_zones")
    op.drop_table("warehouses")
