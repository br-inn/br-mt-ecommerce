"""billing_cancellation — add CANCELLATION billing_type + original_invoice_id (US-ERP-05-01).

Revision ID: 20260602_138
Revises: 20260602_137
Create Date: 2026-06-02

Cambios en ``invoices``:
- Nueva columna ``original_invoice_id UUID`` — referencia a factura origen para
  notas de crédito y cancelaciones.
- Ampliar el CHECK de ``invoice_type`` para incluir 'CANCELLATION'.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "20260602_138"
down_revision = "20260602_137"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Columna original_invoice_id — FK self-referencial nullable
    # ------------------------------------------------------------------
    op.add_column(
        "invoices",
        sa.Column(
            "original_invoice_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("invoices.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 2. Ampliar CHECK de invoice_type para incluir CANCELLATION
    #    Nombre real del constraint en el modelo ORM: ck_invoice_type
    # ------------------------------------------------------------------
    op.drop_constraint("ck_invoice_type", "invoices", type_="check")
    op.create_check_constraint(
        "ck_invoice_type",
        "invoices",
        "invoice_type IN ('STANDARD','CREDIT_MEMO','DEBIT_MEMO','PROFORMA','INTERCOMPANY','CANCELLATION')",
    )

    # ------------------------------------------------------------------
    # 3. Índice para búsquedas por original_invoice_id
    # ------------------------------------------------------------------
    op.create_index(
        "idx_invoice_original_id",
        "invoices",
        ["original_invoice_id"],
        postgresql_where=sa.text("original_invoice_id IS NOT NULL"),
    )


def downgrade() -> None:
    op.drop_index("idx_invoice_original_id", table_name="invoices")
    op.drop_constraint("ck_invoice_type", "invoices", type_="check")
    op.create_check_constraint(
        "ck_invoice_type",
        "invoices",
        "invoice_type IN ('STANDARD','CREDIT_MEMO','DEBIT_MEMO','PROFORMA','INTERCOMPANY')",
    )
    op.drop_column("invoices", "original_invoice_id")
