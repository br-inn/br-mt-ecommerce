"""EP-ERP-02 US-ERP-02-01 — stock_movement_types, stock_movements, journal_entries.

Tablas del catálogo de tipos de movimiento SAP-MM y el diario de movimientos
físicos de stock. journal_entries cubre el asiento contable simple cuando
posts_accounting=true en el tipo de movimiento.

Revision ID: 20260515_105
Revises: 20260513_104
Create Date: 2026-05-15
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260515_105"
down_revision: str = "20260513_104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # stock_movement_types
    # ------------------------------------------------------------------
    op.create_table(
        "stock_movement_types",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column(
            "direction",
            sa.Text(),
            nullable=False,
        ),
        sa.Column("requires_reference", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("posts_accounting", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("direction IN ('IN','OUT','TRANSFER')", name="ck_smt_direction"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_smt_code"),
    )

    # ------------------------------------------------------------------
    # stock_movements  (lot_id FK y warehouse_id FK se añaden en 107/108)
    # ------------------------------------------------------------------
    op.create_table(
        "stock_movements",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("movement_type_id", sa.UUID(), nullable=False),
        sa.Column("product_id", sa.UUID(), nullable=False),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("lot_id", sa.UUID(), nullable=True),        # FK real en mig 107
        sa.Column("warehouse_id", sa.UUID(), nullable=True),  # FK real en mig 108
        sa.Column("location_id", sa.UUID(), nullable=True),
        sa.Column("reference_id", sa.UUID(), nullable=True),
        sa.Column("reference_type", sa.Text(), nullable=True),
        sa.Column("reversal_of", sa.UUID(), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("posted_by", sa.UUID(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("qty <> 0", name="ck_sm_qty_nonzero"),
        sa.CheckConstraint(
            "reference_type IN ('purchase_order','goods_receipt','sale_order') OR reference_type IS NULL",
            name="ck_sm_reference_type",
        ),
        sa.ForeignKeyConstraint(
            ["movement_type_id"], ["stock_movement_types.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["product_id"], ["products.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["reversal_of"], ["stock_movements.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["posted_by"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_sm_product", "stock_movements", ["product_id"])
    op.create_index("idx_sm_type", "stock_movements", ["movement_type_id"])
    op.create_index("idx_sm_posted_at", "stock_movements", ["posted_at"])
    op.create_index("idx_sm_reference", "stock_movements", ["reference_id", "reference_type"])

    # ------------------------------------------------------------------
    # journal_entries
    # ------------------------------------------------------------------
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.UUID(), server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("source_movement_id", sa.UUID(), nullable=False),
        sa.Column("debit_account", sa.Text(), nullable=False),
        sa.Column("credit_account", sa.Text(), nullable=False),
        sa.Column("amount", sa.Numeric(18, 4), nullable=False),
        sa.Column("currency", sa.CHAR(3), nullable=False, server_default=sa.text("'AED'")),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("amount > 0", name="ck_je_amount_pos"),
        sa.ForeignKeyConstraint(
            ["source_movement_id"], ["stock_movements.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_je_movement", "journal_entries", ["source_movement_id"])

    # ------------------------------------------------------------------
    # Seed — tipos de movimiento estándar SAP-MM
    # ------------------------------------------------------------------
    op.execute(
        sa.text(
            """
            INSERT INTO stock_movement_types (code, name, direction, requires_reference, posts_accounting)
            VALUES
                ('101', 'GR vs PO',          'IN',       true,  true),
                ('102', 'Reversal GR vs PO', 'IN',       true,  false),
                ('261', 'GI vs Sales Order', 'OUT',      true,  true),
                ('301', 'Transfer Posting',  'TRANSFER', true,  false),
                ('551', 'Scrap',             'OUT',      false, true),
                ('561', 'Opening Balance',   'IN',       false, false)
            """
        )
    )


def downgrade() -> None:
    op.drop_table("journal_entries")
    op.drop_table("stock_movements")
    op.drop_table("stock_movement_types")
