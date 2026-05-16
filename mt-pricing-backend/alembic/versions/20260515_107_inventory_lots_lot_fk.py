"""EP-ERP-02 US-ERP-02-03 — inventory_lots + FK lot_id en stock_movements e inventory_positions.

Crea la tabla de lotes de inventario (trazabilidad física: número de lote,
caducidad, país de origen, estado de calidad) y materializa las FK que se
dejaron nullable en migraciones anteriores.

Revision ID: 20260515_107
Revises: 20260515_106
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_107"
down_revision: str = "20260515_106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "inventory_lots",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("lot_number", sa.Text(), nullable=False),
        sa.Column("product_sku", sa.Text(), nullable=False),
        sa.Column("manufacture_date", sa.Date(), nullable=True),
        sa.Column("expiry_date", sa.Date(), nullable=True),
        sa.Column("country_of_origin", sa.CHAR(2), nullable=True),
        sa.Column(
            "quality_status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'released'"),
        ),
        sa.Column("po_line_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint(
            "quality_status IN ('released','hold','blocked')",
            name="ck_lot_quality_status",
        ),
        sa.ForeignKeyConstraint(
            ["product_sku"], ["products.sku"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["po_line_id"], ["purchase_order_lines.id"], ondelete="SET NULL"
        ),
        sa.UniqueConstraint("lot_number", "product_sku", name="uq_lot_number_product"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_lots_product", "inventory_lots", ["product_sku"])
    op.create_index("idx_lots_quality_status", "inventory_lots", ["quality_status"])

    # FK lot_id real en stock_movements (columna nullable ya existe desde mig 105)
    op.create_foreign_key(
        "fk_stock_movements_lot",
        "stock_movements",
        "inventory_lots",
        ["lot_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # FK lot_id real en inventory_positions (columna nullable ya existe desde mig 106)
    op.create_foreign_key(
        "fk_inv_pos_lot",
        "inventory_positions",
        "inventory_lots",
        ["lot_id"],
        ["id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    op.drop_constraint("fk_inv_pos_lot", "inventory_positions", type_="foreignkey")
    op.drop_constraint("fk_stock_movements_lot", "stock_movements", type_="foreignkey")
    op.drop_table("inventory_lots")
