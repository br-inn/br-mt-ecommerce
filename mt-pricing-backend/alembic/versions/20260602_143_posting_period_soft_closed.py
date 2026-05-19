"""posting_period_soft_closed — añadir status 'soft_closed' a posting_periods (US-ERP-06-01).

Revision ID: 20260602_143
Revises: 20260602_142
Create Date: 2026-06-02

Cambios en ``posting_periods``:
- Ampliar el CHECK ``ck_posting_periods_status`` para incluir 'soft_closed'.
  Nuevo conjunto: open | soft_closed | closed | locked.
"""
from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260602_143"
down_revision = "20260602_142"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Reemplazar constraint de status — añadir 'soft_closed'
    # ------------------------------------------------------------------
    op.drop_constraint("ck_posting_periods_status", "posting_periods", type_="check")
    op.create_check_constraint(
        "ck_posting_periods_status",
        "posting_periods",
        "status IN ('open','soft_closed','closed','locked')",
    )


def downgrade() -> None:
    # Primero normalizar cualquier valor 'soft_closed' existente a 'open'
    # para no violar el constraint anterior al revertir.
    op.execute(
        "UPDATE posting_periods SET status = 'open' WHERE status = 'soft_closed'"
    )
    op.drop_constraint("ck_posting_periods_status", "posting_periods", type_="check")
    op.create_check_constraint(
        "ck_posting_periods_status",
        "posting_periods",
        "status IN ('open','closed','locked')",
    )
