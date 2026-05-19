"""gl_accounts_completeness — normal_balance + is_active + extended seed (US-ERP-06-01).

Revision ID: 20260602_141
Revises: 20260602_140
Create Date: 2026-06-02

Cambios en ``gl_accounts``:
- Nueva columna ``normal_balance TEXT NOT NULL DEFAULT 'DEBIT'`` con CHECK DEBIT|CREDIT.
- Nueva columna ``is_active BOOLEAN NOT NULL DEFAULT true`` (columna simple, no generated).
- Seed: actualiza normal_balance en cuentas existentes por account_type.
- Seed ampliado: ~30 cuentas adicionales cubriendo rangos 1xxx-6xxx para llegar a 50+.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision = "20260602_141"
down_revision = "20260602_140"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Columna normal_balance
    # ------------------------------------------------------------------
    op.add_column(
        "gl_accounts",
        sa.Column(
            "normal_balance",
            sa.Text(),
            nullable=False,
            server_default=sa.text("'DEBIT'"),
        ),
    )
    op.create_check_constraint(
        "ck_gl_accounts_normal_balance",
        "gl_accounts",
        "normal_balance IN ('DEBIT', 'CREDIT')",
    )

    # ------------------------------------------------------------------
    # 2. Columna is_active
    # ------------------------------------------------------------------
    op.add_column(
        "gl_accounts",
        sa.Column(
            "is_active",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("true"),
        ),
    )

    # ------------------------------------------------------------------
    # 3. Actualizar normal_balance en cuentas existentes según account_type
    #    ASSET, EXPENSE → DEBIT  |  LIABILITY, EQUITY, REVENUE, CONTRA → CREDIT
    # ------------------------------------------------------------------
    op.execute(text("""
        UPDATE gl_accounts
        SET normal_balance = CASE
            WHEN account_type IN ('ASSET', 'EXPENSE') THEN 'DEBIT'
            ELSE 'CREDIT'
        END
    """))

    # ------------------------------------------------------------------
    # 4. Seed ampliado — ~30 cuentas adicionales (rangos 1xxx-6xxx)
    # ------------------------------------------------------------------
    op.execute(text("""
        INSERT INTO gl_accounts (account_code, account_name, account_type, normal_balance, is_reconciling)
        VALUES
            -- 1000-1999 Assets
            ('1010', 'Petty Cash',                         'ASSET',     'DEBIT',  false),
            ('1020', 'Bank Account - AED',                 'ASSET',     'DEBIT',  true),
            ('1030', 'Bank Account - USD',                 'ASSET',     'DEBIT',  true),
            ('1100', 'Accounts Receivable - Trade',        'ASSET',     'DEBIT',  true),
            ('1110', 'Allowance for Doubtful Accounts',    'CONTRA',    'CREDIT', false),
            ('1200', 'Inventory - Finished Goods',         'ASSET',     'DEBIT',  true),
            ('1210', 'Inventory - Raw Materials',          'ASSET',     'DEBIT',  false),
            ('1220', 'Inventory - WIP',                    'ASSET',     'DEBIT',  false),
            ('1300', 'Prepaid Expenses',                   'ASSET',     'DEBIT',  false),
            ('1310', 'VAT Receivable',                     'ASSET',     'DEBIT',  true),
            ('1400', 'Property, Plant & Equipment',        'ASSET',     'DEBIT',  false),
            ('1410', 'Accumulated Depreciation - PPE',     'CONTRA',    'CREDIT', false),
            ('1500', 'Right-of-Use Assets',                'ASSET',     'DEBIT',  false),
            ('1510', 'Accumulated Amortisation - ROU',     'CONTRA',    'CREDIT', false),
            -- 2000-2999 Liabilities
            ('2010', 'Accounts Payable - Trade',           'LIABILITY', 'CREDIT', true),
            ('2020', 'Accrued Liabilities',                'LIABILITY', 'CREDIT', false),
            ('2030', 'VAT Payable',                        'LIABILITY', 'CREDIT', true),
            ('2040', 'Withholding Tax Payable',            'LIABILITY', 'CREDIT', false),
            ('2100', 'Short-Term Loans',                   'LIABILITY', 'CREDIT', false),
            ('2200', 'Lease Liability - Current',          'LIABILITY', 'CREDIT', false),
            ('2300', 'Long-Term Debt',                     'LIABILITY', 'CREDIT', false),
            ('2310', 'Lease Liability - Non-Current',      'LIABILITY', 'CREDIT', false),
            -- 3000-3999 Equity
            ('3010', 'Share Capital',                      'EQUITY',    'CREDIT', false),
            ('3020', 'Retained Earnings',                  'EQUITY',    'CREDIT', false),
            ('3030', 'Dividends Paid',                     'EQUITY',    'DEBIT',  false),
            -- 4000-4999 Revenue
            ('4010', 'Product Sales - B2C',                'REVENUE',   'CREDIT', false),
            ('4020', 'Product Sales - B2B',                'REVENUE',   'CREDIT', false),
            ('4030', 'Freight & Delivery Income',          'REVENUE',   'CREDIT', false),
            ('4040', 'Sales Returns & Allowances',         'CONTRA',    'DEBIT',  false),
            -- 5000-5999 COGS (type=EXPENSE, code 5xxx — diferenciado en mv_copa_summary)
            ('5010', 'Cost of Goods Sold - Products',      'EXPENSE',   'DEBIT',  false),
            ('5020', 'Freight-In',                         'EXPENSE',   'DEBIT',  false),
            ('5030', 'Customs & Import Duties',            'EXPENSE',   'DEBIT',  false),
            -- 6000-6999 Operating Expenses (OPEX)
            ('6010', 'Salaries & Wages',                   'EXPENSE',   'DEBIT',  false),
            ('6020', 'Rent Expense',                       'EXPENSE',   'DEBIT',  false),
            ('6030', 'Depreciation Expense',               'EXPENSE',   'DEBIT',  false),
            ('6040', 'Utilities',                          'EXPENSE',   'DEBIT',  false),
            ('6050', 'Marketing & Advertising',            'EXPENSE',   'DEBIT',  false),
            ('6060', 'IT & Software Subscriptions',        'EXPENSE',   'DEBIT',  false),
            ('6070', 'Professional Fees',                  'EXPENSE',   'DEBIT',  false),
            ('6080', 'Bank Charges & FX Losses',           'EXPENSE',   'DEBIT',  false),
            ('6090', 'Travel & Entertainment',             'EXPENSE',   'DEBIT',  false),
            ('6100', 'Insurance',                          'EXPENSE',   'DEBIT',  false),
            ('6200', 'Corporate Income Tax',               'EXPENSE',   'DEBIT',  false),
            ('6210', 'FX Revaluation Loss',                'EXPENSE',   'DEBIT',  false)
        ON CONFLICT (account_code) DO NOTHING
    """))


def downgrade() -> None:
    # Remove only the seed accounts added in this migration (by code range)
    op.execute(text("""
        DELETE FROM gl_accounts WHERE account_code IN (
            '1010','1020','1030','1100','1110','1200','1210','1220',
            '1300','1310','1400','1410','1500','1510',
            '2010','2020','2030','2040','2100','2200','2300','2310',
            '3010','3020','3030',
            '4010','4020','4030','4040',
            '5010','5020','5030',
            '6010','6020','6030','6040','6050','6060','6070',
            '6080','6090','6100','6200','6210'
        )
    """))
    op.drop_column("gl_accounts", "is_active")
    op.drop_constraint("ck_gl_accounts_normal_balance", "gl_accounts", type_="check")
    op.drop_column("gl_accounts", "normal_balance")
