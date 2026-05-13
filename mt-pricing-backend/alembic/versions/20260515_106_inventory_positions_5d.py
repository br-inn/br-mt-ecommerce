"""EP-ERP-02 US-ERP-02-02 — inventory_positions 5D: stock_type + location_id + product_id + warehouse_id.

Extiende inventory_positions para el modelo 5D (product × warehouse × location × lot × stock_type):
- product_id UUID nullable (join semántico con products.id; el campo legacy sku sigue presente)
- warehouse_id UUID nullable (FK real en mig 108 cuando se crea la tabla warehouses)
- lot_id UUID nullable (FK real en mig 107 cuando se crea inventory_lots)
- location_id UUID nullable (FK real en mig 108 cuando se crea warehouse_locations)
- stock_type: unrestricted | quality_inspection | restricted | in_transit

Revision ID: 20260515_106
Revises: 20260515_105
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_106"
down_revision: str = "20260515_105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inventory_positions",
        sa.Column("product_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "inventory_positions",
        sa.Column("warehouse_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "inventory_positions",
        sa.Column("lot_id", sa.UUID(), nullable=True),  # FK real en mig 107
    )
    op.add_column(
        "inventory_positions",
        sa.Column("location_id", sa.UUID(), nullable=True),
    )
    op.add_column(
        "inventory_positions",
        sa.Column(
            "stock_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'unrestricted'"),
        ),
    )

    # FK product_id → products.id (nullable: filas legacy sin product_id)
    op.create_foreign_key(
        "fk_inv_pos_product",
        "inventory_positions",
        "products",
        ["product_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_check_constraint(
        "ck_inv_pos_stock_type",
        "inventory_positions",
        "stock_type IN ('unrestricted','quality_inspection','restricted','in_transit')",
    )

    # Índice único 5D (solo aplica cuando location_id y lot_id no son NULL)
    op.create_index(
        "uix_inv_pos_5d",
        "inventory_positions",
        ["product_id", "warehouse_id", "location_id", "lot_id", "stock_type"],
        unique=True,
        postgresql_where=sa.text("location_id IS NOT NULL AND lot_id IS NOT NULL"),
    )

    # Índice para consultas de disponibilidad (solo unrestricted)
    op.create_index(
        "ix_inv_pos_unrestricted",
        "inventory_positions",
        ["product_id", "warehouse_id"],
        postgresql_where=sa.text("stock_type = 'unrestricted'"),
    )


def downgrade() -> None:
    op.drop_index("ix_inv_pos_unrestricted", table_name="inventory_positions")
    op.drop_index("uix_inv_pos_5d", table_name="inventory_positions")
    op.drop_constraint("ck_inv_pos_stock_type", "inventory_positions", type_="check")
    op.drop_constraint("fk_inv_pos_product", "inventory_positions", type_="foreignkey")
    op.drop_column("inventory_positions", "stock_type")
    op.drop_column("inventory_positions", "location_id")
    op.drop_column("inventory_positions", "lot_id")
    op.drop_column("inventory_positions", "warehouse_id")
    op.drop_column("inventory_positions", "product_id")
