"""EP-ERP-06 US-ERP-06-01 — Chart of Accounts + Posting Periods.

Revision ID: 20260527_110
Revises: 20260525_115
Create Date: 2026-05-27

Tables: gl_accounts, posting_periods
Seeds: 20 GL accounts representativas + 14 posting periods 2026
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "20260527_110"
down_revision = "20260525_115"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # -------------------------------------------------------------------------
    # gl_accounts — Chart of Accounts
    # -------------------------------------------------------------------------
    op.create_table(
        "gl_accounts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("account_code", sa.Text(), nullable=False),
        sa.Column("account_name", sa.Text(), nullable=False),
        sa.Column("account_type", sa.Text(), nullable=False),
        sa.Column(
            "parent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("gl_accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("is_reconciling", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("is_blocked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("currency", sa.CHAR(3), server_default="AED", nullable=False),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "account_type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE','CONTRA')",
            name="ck_gl_accounts_account_type",
        ),
        sa.UniqueConstraint("account_code", name="uq_gl_accounts_code"),
    )
    op.create_index("ix_gl_accounts_code", "gl_accounts", ["account_code"])
    op.create_index("ix_gl_accounts_type", "gl_accounts", ["account_type"])

    # -------------------------------------------------------------------------
    # posting_periods
    # -------------------------------------------------------------------------
    op.create_table(
        "posting_periods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            server_default=sa.text("gen_random_uuid()"),
            primary_key=True,
        ),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("period_num", sa.Integer(), nullable=False),
        sa.Column("period_name", sa.Text(), nullable=True),
        sa.Column("date_from", sa.Date(), nullable=False),
        sa.Column("date_to", sa.Date(), nullable=False),
        sa.Column("status", sa.Text(), server_default="open", nullable=False),
        sa.Column("closed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column(
            "closed_by",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.CheckConstraint("period_num BETWEEN 1 AND 16", name="ck_posting_periods_period_num"),
        sa.CheckConstraint(
            "status IN ('open','closed','locked')", name="ck_posting_periods_status"
        ),
        sa.UniqueConstraint("fiscal_year", "period_num", name="uq_posting_periods_fy_period"),
    )
    op.create_index("ix_posting_periods_fy", "posting_periods", ["fiscal_year", "period_num"])

    # -------------------------------------------------------------------------
    # Seed: gl_accounts
    # -------------------------------------------------------------------------
    op.execute("""
        INSERT INTO gl_accounts (id, account_code, account_name, account_type, currency) VALUES
        (gen_random_uuid(), '1000', 'Activo Corriente', 'ASSET', 'AED'),
        (gen_random_uuid(), '1100', 'Cuentas por Cobrar', 'ASSET', 'AED'),
        (gen_random_uuid(), '1200', 'Inventario', 'ASSET', 'AED'),
        (gen_random_uuid(), '1300', 'Otros Activos Corrientes', 'ASSET', 'AED'),
        (gen_random_uuid(), '2000', 'Pasivo Corriente', 'LIABILITY', 'AED'),
        (gen_random_uuid(), '2100', 'Cuentas por Pagar', 'LIABILITY', 'AED'),
        (gen_random_uuid(), '2200', 'IVA por Pagar', 'LIABILITY', 'AED'),
        (gen_random_uuid(), '2300', 'Otros Pasivos', 'LIABILITY', 'AED'),
        (gen_random_uuid(), '3000', 'Capital Social', 'EQUITY', 'AED'),
        (gen_random_uuid(), '4100', 'Ingresos por Ventas', 'REVENUE', 'AED'),
        (gen_random_uuid(), '4200', 'Ingresos B2C AE', 'REVENUE', 'AED'),
        (gen_random_uuid(), '4300', 'Ingresos B2C SA', 'REVENUE', 'SAR'),
        (gen_random_uuid(), '5100', 'COGS', 'EXPENSE', 'AED'),
        (gen_random_uuid(), '5200', 'Costos Logística', 'EXPENSE', 'AED'),
        (gen_random_uuid(), '6100', 'Gastos Ventas', 'EXPENSE', 'AED'),
        (gen_random_uuid(), '6200', 'Gastos Marketing', 'EXPENSE', 'AED'),
        (gen_random_uuid(), '6300', 'Gastos IT', 'EXPENSE', 'AED'),
        (gen_random_uuid(), '6400', 'G&A', 'EXPENSE', 'AED'),
        (gen_random_uuid(), '7100', 'Diferencias de Cambio', 'EXPENSE', 'AED'),
        (gen_random_uuid(), '7200', 'Intereses', 'EXPENSE', 'AED'),
        (gen_random_uuid(), '8100', 'Impuesto Corporativo UAE (CIT)', 'EXPENSE', 'AED')
    """)

    # -------------------------------------------------------------------------
    # Seed: posting_periods 2026 (12 meses + período 13 ajustes + período 14 cierre)
    # -------------------------------------------------------------------------
    op.execute("""
        INSERT INTO posting_periods (id, fiscal_year, period_num, period_name, date_from, date_to, status) VALUES
        (gen_random_uuid(), 2026,  1, 'Ene 2026', '2026-01-01', '2026-01-31', 'closed'),
        (gen_random_uuid(), 2026,  2, 'Feb 2026', '2026-02-01', '2026-02-28', 'closed'),
        (gen_random_uuid(), 2026,  3, 'Mar 2026', '2026-03-01', '2026-03-31', 'closed'),
        (gen_random_uuid(), 2026,  4, 'Abr 2026', '2026-04-01', '2026-04-30', 'closed'),
        (gen_random_uuid(), 2026,  5, 'May 2026', '2026-05-01', '2026-05-31', 'open'),
        (gen_random_uuid(), 2026,  6, 'Jun 2026', '2026-06-01', '2026-06-30', 'open'),
        (gen_random_uuid(), 2026,  7, 'Jul 2026', '2026-07-01', '2026-07-31', 'open'),
        (gen_random_uuid(), 2026,  8, 'Ago 2026', '2026-08-01', '2026-08-31', 'open'),
        (gen_random_uuid(), 2026,  9, 'Sep 2026', '2026-09-01', '2026-09-30', 'open'),
        (gen_random_uuid(), 2026, 10, 'Oct 2026', '2026-10-01', '2026-10-31', 'open'),
        (gen_random_uuid(), 2026, 11, 'Nov 2026', '2026-11-01', '2026-11-30', 'open'),
        (gen_random_uuid(), 2026, 12, 'Dic 2026', '2026-12-01', '2026-12-31', 'open'),
        (gen_random_uuid(), 2026, 13, 'Ajustes 2026', '2026-12-31', '2026-12-31', 'open'),
        (gen_random_uuid(), 2026, 14, 'Cierre 2026', '2026-12-31', '2026-12-31', 'open')
    """)


def downgrade() -> None:
    op.execute("DELETE FROM posting_periods WHERE fiscal_year = 2026")
    op.execute("DELETE FROM gl_accounts")
    op.drop_index("ix_posting_periods_fy", table_name="posting_periods")
    op.drop_table("posting_periods")
    op.drop_index("ix_gl_accounts_type", table_name="gl_accounts")
    op.drop_index("ix_gl_accounts_code", table_name="gl_accounts")
    op.drop_table("gl_accounts")
