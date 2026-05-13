"""approval_rules — EP-ERP-03 US-ERP-03-02.

Tabla approval_rules para enrutamiento configurable de aprobaciones.
Seed inicial con 3 reglas: auto-approve <1000, gerente 1000-10000, ti >10000.

Revision ID: 20260516_106
Revises: 20260516_105
Create Date: 2026-05-16
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op


revision: str = "20260516_106"
down_revision: str = "20260516_105"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE approval_rules (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            document_type TEXT NOT NULL DEFAULT 'purchase_requisition',
            min_amount NUMERIC(18,4) NOT NULL DEFAULT 0,
            max_amount NUMERIC(18,4),
            category_id TEXT,
            approver_role TEXT,
            approver_user_id UUID REFERENCES auth.users(id),
            timeout_hours INT NOT NULL DEFAULT 48,
            priority INT NOT NULL DEFAULT 0,
            is_active BOOL DEFAULT true,
            created_at TIMESTAMPTZ DEFAULT NOW()
        );
    """)

    op.execute("""
        CREATE INDEX idx_approval_rules_lookup
            ON approval_rules(document_type, priority, is_active)
            WHERE is_active = true;
    """)

    op.execute("""
        INSERT INTO approval_rules
            (document_type, min_amount, max_amount, approver_role, timeout_hours, priority)
        VALUES
            ('purchase_requisition', 0,     1000,  NULL,      0,  0),
            ('purchase_requisition', 1000,  10000, 'gerente', 48, 1),
            ('purchase_requisition', 10000, NULL,  'ti',      72, 2);
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS approval_rules;")
