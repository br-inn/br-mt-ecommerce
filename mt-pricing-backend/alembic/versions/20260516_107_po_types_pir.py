"""po_types_pir — EP-ERP-03 US-ERP-03-03.

Cambios:
- ADD COLUMN purchase_orders.po_type (STANDARD/BLANKET/CONTRACT/SCHEDULING).
- ADD COLUMN purchase_order_lines.price_source ('manual'/'pir').
- CREATE TABLE vendor_product_conditions (Purchasing Info Records).

Revision ID: 20260516_107
Revises: 20260516_106
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260516_107"
down_revision: str = "20260516_106"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE purchase_orders
            ADD COLUMN po_type TEXT NOT NULL DEFAULT 'STANDARD'
                CHECK (po_type IN ('STANDARD','BLANKET','CONTRACT','SCHEDULING'));
    """)

    op.execute("""
        ALTER TABLE purchase_order_lines
            ADD COLUMN price_source TEXT NOT NULL DEFAULT 'manual'
                CHECK (price_source IN ('manual','pir'));
    """)

    op.execute("""
        CREATE TABLE vendor_product_conditions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            vendor_id TEXT NOT NULL,
            product_sku TEXT NOT NULL REFERENCES products(sku),
            price NUMERIC(18,4) NOT NULL,
            uom TEXT NOT NULL DEFAULT 'UNIT',
            moq INT NOT NULL DEFAULT 1,
            lead_time_days INT,
            valid_from DATE NOT NULL DEFAULT CURRENT_DATE,
            valid_to DATE,
            currency CHAR(3) NOT NULL DEFAULT 'AED',
            is_active BOOL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            UNIQUE(vendor_id, product_sku, valid_from)
        );
    """)

    op.execute("""
        CREATE INDEX idx_vpc_vendor_product
            ON vendor_product_conditions(vendor_id, product_sku)
            WHERE is_active = true;
    """)
    op.execute("""
        CREATE INDEX idx_vpc_validity
            ON vendor_product_conditions(valid_from, valid_to)
            WHERE is_active = true;
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS vendor_product_conditions;")
    op.execute("""
        ALTER TABLE purchase_order_lines DROP COLUMN IF EXISTS price_source;
    """)
    op.execute("""
        ALTER TABLE purchase_orders DROP COLUMN IF EXISTS po_type;
    """)
