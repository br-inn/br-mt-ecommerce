"""purchase_requisitions — EP-ERP-03 US-ERP-03-01.

Tablas:
- purchase_requisitions: solicitudes internas de compra con lifecycle
  draft → pending_approval → approved/rejected/cancelled/converted_to_po.
- approval_decisions: registro inmutable de decisiones de aprobación
  (APPROVE/REJECT) para trazabilidad. Sin UPDATE/DELETE por diseño.

Revision ID: 20260516_105
Revises: 20260513_104
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260516_105"
down_revision: str = "20260513_104"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE purchase_requisitions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            pr_number TEXT NOT NULL UNIQUE,
            requester_id UUID NOT NULL REFERENCES auth.users(id),
            product_sku TEXT REFERENCES products(sku),
            qty NUMERIC(18,4) NOT NULL,
            uom TEXT NOT NULL DEFAULT 'UNIT',
            required_date DATE,
            cost_center_id TEXT,
            suggested_vendor_id UUID,
            estimated_amount NUMERIC(18,4),
            status TEXT NOT NULL DEFAULT 'draft'
                CHECK (status IN (
                    'draft','pending_approval','approved',
                    'rejected','cancelled','converted_to_po'
                )),
            notes TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX idx_pr_requester ON purchase_requisitions(requester_id);
    """)
    op.execute("""
        CREATE INDEX idx_pr_status ON purchase_requisitions(status)
            WHERE status NOT IN ('cancelled','converted_to_po');
    """)
    op.execute("""
        CREATE INDEX idx_pr_product ON purchase_requisitions(product_sku)
            WHERE product_sku IS NOT NULL;
    """)

    op.execute("""
        CREATE TABLE approval_decisions (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_id UUID NOT NULL,
            document_type TEXT NOT NULL DEFAULT 'purchase_requisition',
            approver_id UUID NOT NULL REFERENCES auth.users(id),
            action TEXT NOT NULL CHECK (action IN ('APPROVE','REJECT','ESCALATE')),
            reason TEXT,
            decided_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX idx_ad_document ON approval_decisions(document_id, document_type);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS approval_decisions;")
    op.execute("DROP TABLE IF EXISTS purchase_requisitions;")
