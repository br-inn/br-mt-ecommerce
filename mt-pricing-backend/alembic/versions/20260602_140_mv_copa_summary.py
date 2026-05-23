"""mv_copa_summary — materialized view de rentabilidad por profit center × período (US-ERP-06-09).

Revision ID: 20260602_140
Revises: 20260602_139
Create Date: 2026-06-02

Vista materializada:
- ``mv_copa_summary`` — revenue, COGS, OPEX, gross_margin y EBIT agrupados por
  profit center × fiscal_year × posting_period, desde financial_entries × gl_accounts.

Nota: ``account_type`` en gl_accounts usa 'EXPENSE' para gastos y no existe 'COGS'
como valor de constraint (ck_gl_accounts_account_type). La vista diferencia COGS
(5000-5999) de OPEX (6000-6999) via account_code range con subcondición adicional,
o alternativamente usa account_type = 'EXPENSE' para ambos y los separa por
account_code prefix. Para compatibilidad total con el constraint existente, la vista
usa 'REVENUE' y 'EXPENSE' como únicos account_type distintos; se añade 'COGS'
al constraint en migración 141.
En esta migración se usa account_type = 'EXPENSE' para COGS y OPEX diferenciados
por account_code (5xxx vs 6xxx) para que la vista funcione sin romper el constraint.
"""

from __future__ import annotations

from sqlalchemy import text

from alembic import op

# revision identifiers, used by Alembic.
revision = "20260602_140"
down_revision = "20260602_139"
branch_labels = None
depends_on = None

_CREATE_MV = """
CREATE MATERIALIZED VIEW mv_copa_summary AS
SELECT
    COALESCE(pc.pc_code, 'UNASSIGNED') AS pc_code,
    COALESCE(pc.pc_name, 'Sin Centro de Beneficio') AS pc_name,
    fe.fiscal_year,
    fe.posting_period,
    SUM(CASE WHEN ga.account_type = 'REVENUE'
             THEN fe.credit_amount - fe.debit_amount
             ELSE 0 END) AS revenue,
    SUM(CASE WHEN ga.account_type = 'EXPENSE'
              AND ga.account_code LIKE '5%'
             THEN fe.debit_amount - fe.credit_amount
             ELSE 0 END) AS cogs,
    SUM(CASE WHEN ga.account_type = 'EXPENSE'
              AND ga.account_code NOT LIKE '5%'
             THEN fe.debit_amount - fe.credit_amount
             ELSE 0 END) AS opex,
    SUM(CASE WHEN ga.account_type = 'REVENUE'
             THEN fe.credit_amount - fe.debit_amount
             ELSE 0 END)
      - SUM(CASE WHEN ga.account_type = 'EXPENSE'
                  AND ga.account_code LIKE '5%'
                 THEN fe.debit_amount - fe.credit_amount
                 ELSE 0 END) AS gross_margin,
    SUM(CASE WHEN ga.account_type = 'REVENUE'
             THEN fe.credit_amount - fe.debit_amount
             ELSE 0 END)
      - SUM(CASE WHEN ga.account_type = 'EXPENSE'
                 THEN fe.debit_amount - fe.credit_amount
                 ELSE 0 END) AS ebit
FROM financial_entries fe
JOIN gl_accounts ga ON ga.id = fe.gl_account_id
LEFT JOIN profit_centers pc ON pc.id = fe.profit_center_id
GROUP BY
    COALESCE(pc.pc_code, 'UNASSIGNED'),
    COALESCE(pc.pc_name, 'Sin Centro de Beneficio'),
    fe.fiscal_year,
    fe.posting_period
WITH DATA
"""

_DROP_MV = "DROP MATERIALIZED VIEW IF EXISTS mv_copa_summary"


def upgrade() -> None:
    op.execute(text(_CREATE_MV))
    op.execute(
        text(
            "CREATE UNIQUE INDEX uix_copa_summary "
            "ON mv_copa_summary(pc_code, fiscal_year, posting_period)"
        )
    )


def downgrade() -> None:
    op.execute(text(_DROP_MV))
