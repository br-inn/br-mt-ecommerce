"""inv_purchase_orders — tabla purchase_orders (EP-INV-01 / US-INV-01-01).

Revision ID: 090
Revises: 076
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision = "090"
down_revision = "20260512_086"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "purchase_orders",
        sa.Column(
            "id",
            sa.UUID(),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("po_number", sa.String(64), nullable=False),
        sa.Column(
            "supplier_code",
            sa.String(64),
            sa.ForeignKey("suppliers.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.String(32),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "currency",
            sa.String(3),
            sa.ForeignKey("currencies.code", ondelete="RESTRICT"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_by",
            sa.UUID(),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
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
        sa.CheckConstraint(
            "status IN ('draft','confirmed','partial','received','cancelled')",
            name="ck_po_status",
        ),
        sa.UniqueConstraint("po_number", name="uq_po_number"),
    )

    op.create_index("idx_po_supplier", "purchase_orders", ["supplier_code", "status"])
    op.create_index(
        "idx_po_status",
        "purchase_orders",
        ["status"],
        postgresql_where=sa.text("status NOT IN ('received','cancelled')"),
    )


def downgrade() -> None:
    op.drop_index("idx_po_status", table_name="purchase_orders")
    op.drop_index("idx_po_supplier", table_name="purchase_orders")
    op.drop_table("purchase_orders")
