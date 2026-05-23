"""Sales Orders + Lines — O2C document chain (US-ERP-04-01).

Revision ID: 20260524_110
Revises: 20260517_109
Create Date: 2026-05-24
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

# revision identifiers
revision = "20260524_110"
down_revision = "20260517_109"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # sales_orders
    # ------------------------------------------------------------------
    op.create_table(
        "sales_orders",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column("so_number", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.Text(), nullable=False),
        sa.Column(
            "order_type",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'STANDARD'"),
        ),
        sa.Column("quotation_id", sa.UUID(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'draft'"),
        ),
        sa.Column(
            "warehouse_id",
            sa.UUID(),
            sa.ForeignKey("warehouses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column("payment_terms", sa.Text(), nullable=True),
        sa.Column("currency", sa.CHAR(3), nullable=True, server_default=sa.text("'AED'")),
        sa.Column("subtotal", sa.Numeric(18, 4), nullable=True),
        sa.Column("tax_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("total_amount", sa.Numeric(18, 4), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.PrimaryKeyConstraint("id", name="pk_sales_orders"),
        sa.UniqueConstraint("so_number", name="uq_so_number"),
        sa.CheckConstraint(
            "order_type IN ('STANDARD','RUSH','CASH','CONTRACT_RELEASE','RETURN')",
            name="ck_so_order_type",
        ),
        sa.CheckConstraint(
            "status IN ('draft','confirmed','in_fulfillment','partially_delivered','delivered','invoiced','closed','cancelled','on_credit_hold')",
            name="ck_so_status",
        ),
    )
    op.create_index("idx_so_customer_id", "sales_orders", ["customer_id"])
    op.create_index("idx_so_status", "sales_orders", ["status"])
    op.create_index("idx_so_created_at", "sales_orders", ["created_at"])

    # ------------------------------------------------------------------
    # sales_order_lines
    # ------------------------------------------------------------------
    op.create_table(
        "sales_order_lines",
        sa.Column("id", sa.UUID(), nullable=False, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "so_id",
            sa.UUID(),
            sa.ForeignKey("sales_orders.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "product_sku",
            sa.Text(),
            sa.ForeignKey("products.sku", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("qty", sa.Numeric(18, 4), nullable=False),
        sa.Column("uom", sa.Text(), nullable=False, server_default=sa.text("'UNIT'")),
        sa.Column("unit_price", sa.Numeric(18, 4), nullable=True),
        sa.Column("discount_pct", sa.Numeric(5, 2), nullable=False, server_default=sa.text("0")),
        # line_total computed server-side via trigger / view; stored for simplicity
        sa.Column("line_total", sa.Numeric(18, 4), nullable=True),
        sa.Column("confirmed_qty", sa.Numeric(18, 4), nullable=True),
        sa.Column("requested_delivery_date", sa.Date(), nullable=True),
        sa.Column(
            "status",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'open'"),
        ),
        sa.PrimaryKeyConstraint("id", name="pk_sales_order_lines"),
        sa.CheckConstraint(
            "status IN ('open','confirmed','partially_delivered','delivered','cancelled')",
            name="ck_sol_status",
        ),
    )
    op.create_index("idx_sol_so_id", "sales_order_lines", ["so_id"])
    op.create_index("idx_sol_product_sku", "sales_order_lines", ["product_sku"])

    # Trigger to keep updated_at current on sales_orders
    op.execute("""
        CREATE OR REPLACE FUNCTION set_updated_at_sales_orders()
        RETURNS TRIGGER LANGUAGE plpgsql AS $$
        BEGIN
            NEW.updated_at = now();
            RETURN NEW;
        END;
        $$;
    """)
    op.execute("""
        CREATE TRIGGER trg_so_updated_at
        BEFORE UPDATE ON sales_orders
        FOR EACH ROW EXECUTE FUNCTION set_updated_at_sales_orders();
    """)


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_so_updated_at ON sales_orders")
    op.execute("DROP FUNCTION IF EXISTS set_updated_at_sales_orders()")
    op.drop_table("sales_order_lines")
    op.drop_table("sales_orders")
