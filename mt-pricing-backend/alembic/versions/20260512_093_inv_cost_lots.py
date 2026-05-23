"""inv_cost_lots — tabla cost_lots (EP-INV-01 / US-INV-01-01).

Revision ID: 093
Revises: 092
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "093"
down_revision = "092"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cost_lots",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column(
            "sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("supplier_code", sa.String(64), nullable=False),
        sa.Column(
            "scheme_code",
            sa.String(32),
            sa.ForeignKey("schemes.code", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "gr_id",
            sa.UUID(),
            sa.ForeignKey("goods_receipts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty_original", sa.Numeric(12, 3), nullable=False),
        sa.Column("qty_remaining", sa.Numeric(12, 3), nullable=False),
        sa.Column("unit_cost_aed", sa.Numeric(18, 4), nullable=False),
        sa.Column(
            "effective_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
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
        sa.CheckConstraint("qty_original > 0", name="ck_cl_qty_original_pos"),
        sa.CheckConstraint("qty_remaining >= 0", name="ck_cl_qty_remaining_nonneg"),
        sa.CheckConstraint("unit_cost_aed >= 0", name="ck_cl_unit_cost_nonneg"),
        sa.CheckConstraint(
            "qty_remaining <= qty_original", name="ck_cl_qty_remaining_lte_original"
        ),
    )

    op.create_index("idx_cost_lots_lookup", "cost_lots", ["sku", "supplier_code", "scheme_code"])
    op.create_index("idx_cost_lots_gr", "cost_lots", ["gr_id"])


def downgrade() -> None:
    op.drop_index("idx_cost_lots_gr", table_name="cost_lots")
    op.drop_index("idx_cost_lots_lookup", table_name="cost_lots")
    op.drop_table("cost_lots")
