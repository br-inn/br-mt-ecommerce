"""gl_accounts_extended_seed — ~150 additional GL accounts for a full chart of accounts.

Extends the chart seeded in migs 20260527_110 and 20260602_141 to reach 200+ accounts
covering sub-account ranges across all account type groups:
  1100-1900: Cash sub-accounts, Receivables, Inventory lines, Prepaid, Fixed Assets
  2100-2900: AP sub-accounts, Accruals, Deferred Revenue, Short/Long-term debt lines
  3100-3900: Share Capital variants, Retained Earnings, Other Equity
  4100-4900: Product Revenue lines, Service Revenue, Other Income, Discounts (contra)
  5100-5900: COGS lines, Direct Labor, Freight, Import Duties
  6100-6900: Salaries detail, Rent, Utilities, Marketing, IT, Depreciation, Amortization

All inserts use ON CONFLICT (account_code) DO NOTHING for idempotency.
Downgrade: no-op — removing seeded accounts risks breaking FK references.

Revision ID: 20260519_149
Revises: 20260519_148
Create Date: 2026-05-19
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op
from sqlalchemy import text

revision: str = "20260519_149"
down_revision: str | None = "20260519_148"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute(text("""
        INSERT INTO gl_accounts
            (account_code, account_name, account_type, normal_balance, is_active)
        VALUES
            -- ---------------------------------------------------------------
            -- 1100-1900: Assets — Cash, Receivables, Inventory, Prepaid, FA
            -- ---------------------------------------------------------------
            ('1101', 'Cash on Hand - Petty Fund AED',              'ASSET',     'DEBIT',  true),
            ('1102', 'Cash on Hand - Petty Fund USD',              'ASSET',     'DEBIT',  true),
            ('1103', 'Cash on Hand - Petty Fund EUR',              'ASSET',     'DEBIT',  true),
            ('1121', 'Bank Account - USD Clearing',                'ASSET',     'DEBIT',  true),
            ('1122', 'Bank Account - EUR',                         'ASSET',     'DEBIT',  true),
            ('1123', 'Bank Account - GBP',                         'ASSET',     'DEBIT',  true),
            ('1124', 'Bank Account - CNY',                         'ASSET',     'DEBIT',  true),
            ('1130', 'Cheques in Transit',                         'ASSET',     'DEBIT',  true),
            ('1140', 'Credit Card Clearing',                       'ASSET',     'DEBIT',  true),
            ('1150', 'Short-Term Deposits',                        'ASSET',     'DEBIT',  true),
            ('1160', 'Margin Deposits',                            'ASSET',     'DEBIT',  true),
            ('1201', 'Trade Receivables - Domestic',               'ASSET',     'DEBIT',  true),
            ('1202', 'Trade Receivables - Export',                 'ASSET',     'DEBIT',  true),
            ('1203', 'Trade Receivables - Intercompany',           'ASSET',     'DEBIT',  true),
            ('1211', 'Allowance for Doubtful - Domestic',          'CONTRA',    'CREDIT', true),
            ('1212', 'Allowance for Doubtful - Export',            'CONTRA',    'CREDIT', true),
            ('1220', 'Employee Advances Receivable',               'ASSET',     'DEBIT',  true),
            ('1230', 'Supplier Advance Payments',                  'ASSET',     'DEBIT',  true),
            ('1240', 'Security Deposits - Landlord',               'ASSET',     'DEBIT',  true),
            ('1250', 'Security Deposits - Other',                  'ASSET',     'DEBIT',  true),
            ('1301', 'Inventory - Trading Goods',                  'ASSET',     'DEBIT',  true),
            ('1302', 'Inventory - Spare Parts',                    'ASSET',     'DEBIT',  true),
            ('1303', 'Inventory - Packaging Materials',            'ASSET',     'DEBIT',  true),
            ('1304', 'Inventory - Consignment Stock',              'ASSET',     'DEBIT',  true),
            ('1305', 'Inventory Adjustment Reserve',               'CONTRA',    'CREDIT', true),
            ('1311', 'Prepaid Insurance',                          'ASSET',     'DEBIT',  true),
            ('1312', 'Prepaid Rent',                               'ASSET',     'DEBIT',  true),
            ('1313', 'Prepaid Subscriptions',                      'ASSET',     'DEBIT',  true),
            ('1320', 'Deferred Marketing Costs',                   'ASSET',     'DEBIT',  true),
            ('1401', 'Land',                                       'ASSET',     'DEBIT',  true),
            ('1402', 'Buildings',                                   'ASSET',     'DEBIT',  true),
            ('1403', 'Machinery & Equipment',                      'ASSET',     'DEBIT',  true),
            ('1404', 'Vehicles',                                    'ASSET',     'DEBIT',  true),
            ('1405', 'Furniture & Fixtures',                       'ASSET',     'DEBIT',  true),
            ('1406', 'Computers & IT Equipment',                   'ASSET',     'DEBIT',  true),
            ('1411', 'Accum Depr - Buildings',                     'CONTRA',    'CREDIT', true),
            ('1412', 'Accum Depr - Machinery',                     'CONTRA',    'CREDIT', true),
            ('1413', 'Accum Depr - Vehicles',                      'CONTRA',    'CREDIT', true),
            ('1414', 'Accum Depr - Computers',                     'CONTRA',    'CREDIT', true),
            ('1501', 'Intangible Assets - Software Licences',      'ASSET',     'DEBIT',  true),
            ('1502', 'Intangible Assets - Trademarks',             'ASSET',     'DEBIT',  true),
            ('1503', 'Intangible Assets - Customer Lists',         'ASSET',     'DEBIT',  true),
            ('1511', 'Accum Amort - Software',                     'CONTRA',    'CREDIT', true),
            ('1512', 'Accum Amort - Trademarks',                   'CONTRA',    'CREDIT', true),
            ('1600', 'Investment in Associates',                   'ASSET',     'DEBIT',  true),
            ('1610', 'Long-Term Receivables',                      'ASSET',     'DEBIT',  true),
            ('1620', 'Deferred Tax Asset',                         'ASSET',     'DEBIT',  true),
            -- ---------------------------------------------------------------
            -- 2100-2900: Liabilities — AP, Accruals, Deferred, Debt
            -- ---------------------------------------------------------------
            ('2011', 'Accounts Payable - Suppliers AED',           'LIABILITY', 'CREDIT', true),
            ('2012', 'Accounts Payable - Suppliers USD',           'LIABILITY', 'CREDIT', true),
            ('2013', 'Accounts Payable - Intercompany',            'LIABILITY', 'CREDIT', true),
            ('2021', 'Accrued Salaries & Wages',                   'LIABILITY', 'CREDIT', true),
            ('2022', 'Accrued Vacation Pay',                       'LIABILITY', 'CREDIT', true),
            ('2023', 'Accrued End-of-Service Benefits',            'LIABILITY', 'CREDIT', true),
            ('2024', 'Accrued Interest',                           'LIABILITY', 'CREDIT', true),
            ('2025', 'Accrued Utilities',                          'LIABILITY', 'CREDIT', true),
            ('2031', 'VAT Payable - Standard Rate',                'LIABILITY', 'CREDIT', true),
            ('2032', 'VAT Collected - E-Commerce',                 'LIABILITY', 'CREDIT', true),
            ('2041', 'WHT Payable - Domestic',                     'LIABILITY', 'CREDIT', true),
            ('2042', 'WHT Payable - Foreign Vendors',              'LIABILITY', 'CREDIT', true),
            ('2050', 'Customer Advances Received',                 'LIABILITY', 'CREDIT', true),
            ('2060', 'Deferred Revenue - Subscriptions',           'LIABILITY', 'CREDIT', true),
            ('2061', 'Deferred Revenue - Maintenance',             'LIABILITY', 'CREDIT', true),
            ('2062', 'Deferred Revenue - Other',                   'LIABILITY', 'CREDIT', true),
            ('2101', 'Short-Term Bank Loans - AED',                'LIABILITY', 'CREDIT', true),
            ('2102', 'Short-Term Bank Loans - USD',                'LIABILITY', 'CREDIT', true),
            ('2110', 'Current Portion of Long-Term Debt',          'LIABILITY', 'CREDIT', true),
            ('2201', 'Lease Liability - Equipment',                'LIABILITY', 'CREDIT', true),
            ('2202', 'Lease Liability - Vehicles',                 'LIABILITY', 'CREDIT', true),
            ('2301', 'Long-Term Bank Loans - AED',                 'LIABILITY', 'CREDIT', true),
            ('2302', 'Long-Term Bank Loans - USD',                 'LIABILITY', 'CREDIT', true),
            ('2311', 'Lease Liability Non-Current - Equipment',    'LIABILITY', 'CREDIT', true),
            ('2320', 'Deferred Tax Liability',                     'LIABILITY', 'CREDIT', true),
            ('2330', 'Pension Obligation',                         'LIABILITY', 'CREDIT', true),
            -- ---------------------------------------------------------------
            -- 3100-3900: Equity
            -- ---------------------------------------------------------------
            ('3011', 'Ordinary Share Capital',                     'EQUITY',    'CREDIT', true),
            ('3012', 'Preference Share Capital',                   'EQUITY',    'CREDIT', true),
            ('3021', 'Retained Earnings - Prior Years',            'EQUITY',    'CREDIT', true),
            ('3022', 'Retained Earnings - Current Year',           'EQUITY',    'CREDIT', true),
            ('3031', 'Dividends Declared',                         'EQUITY',    'DEBIT',  true),
            ('3040', 'Share Premium',                              'EQUITY',    'CREDIT', true),
            ('3050', 'Legal Reserve',                              'EQUITY',    'CREDIT', true),
            ('3060', 'Foreign Currency Translation Reserve',       'EQUITY',    'CREDIT', true),
            ('3070', 'Revaluation Surplus',                        'EQUITY',    'CREDIT', true),
            ('3080', 'Treasury Shares',                            'EQUITY',    'DEBIT',  true),
            -- ---------------------------------------------------------------
            -- 4100-4900: Revenue
            -- ---------------------------------------------------------------
            ('4011', 'Product Sales - UAE B2C',                    'REVENUE',   'CREDIT', true),
            ('4012', 'Product Sales - GCC Export',                 'REVENUE',   'CREDIT', true),
            ('4013', 'Product Sales - Online Marketplace',         'REVENUE',   'CREDIT', true),
            ('4021', 'Product Sales - Wholesale B2B',              'REVENUE',   'CREDIT', true),
            ('4022', 'Product Sales - Government Contracts',       'REVENUE',   'CREDIT', true),
            ('4031', 'Freight Income - Standard',                  'REVENUE',   'CREDIT', true),
            ('4032', 'Freight Income - Express',                   'REVENUE',   'CREDIT', true),
            ('4033', 'Installation & Commissioning Income',        'REVENUE',   'CREDIT', true),
            ('4041', 'Sales Returns - Domestic',                   'CONTRA',    'DEBIT',  true),
            ('4042', 'Sales Returns - Export',                     'CONTRA',    'DEBIT',  true),
            ('4043', 'Sales Discounts - Volume',                   'CONTRA',    'DEBIT',  true),
            ('4044', 'Sales Discounts - Promotional',              'CONTRA',    'DEBIT',  true),
            ('4050', 'Service Revenue - Maintenance Contracts',    'REVENUE',   'CREDIT', true),
            ('4060', 'License Revenue',                            'REVENUE',   'CREDIT', true),
            ('4070', 'Royalty Income',                             'REVENUE',   'CREDIT', true),
            ('4080', 'Interest Income',                            'REVENUE',   'CREDIT', true),
            ('4090', 'FX Gain - Realised',                         'REVENUE',   'CREDIT', true),
            ('4091', 'FX Gain - Unrealised',                       'REVENUE',   'CREDIT', true),
            ('4100', 'Grant Income',                               'REVENUE',   'CREDIT', true),
            ('4110', 'Other Operating Income',                     'REVENUE',   'CREDIT', true),
            -- ---------------------------------------------------------------
            -- 5100-5900: COGS
            -- ---------------------------------------------------------------
            ('5011', 'COGS - Trading Goods B2C',                   'EXPENSE',   'DEBIT',  true),
            ('5012', 'COGS - Trading Goods B2B',                   'EXPENSE',   'DEBIT',  true),
            ('5013', 'COGS - Marketplace Fulfilment',              'EXPENSE',   'DEBIT',  true),
            ('5021', 'Freight-In - Air Cargo',                     'EXPENSE',   'DEBIT',  true),
            ('5022', 'Freight-In - Sea Cargo',                     'EXPENSE',   'DEBIT',  true),
            ('5023', 'Freight-In - Land Transport',                'EXPENSE',   'DEBIT',  true),
            ('5031', 'Customs Duty - Import',                      'EXPENSE',   'DEBIT',  true),
            ('5032', 'Port & Handling Charges',                    'EXPENSE',   'DEBIT',  true),
            ('5033', 'Customs Brokerage Fees',                     'EXPENSE',   'DEBIT',  true),
            ('5040', 'Direct Labor - Warehouse Picking',           'EXPENSE',   'DEBIT',  true),
            ('5041', 'Direct Labor - Assembly',                    'EXPENSE',   'DEBIT',  true),
            ('5050', 'Packaging Materials Used',                   'EXPENSE',   'DEBIT',  true),
            ('5060', 'Inventory Write-Off',                        'EXPENSE',   'DEBIT',  true),
            ('5061', 'Inventory Scrap Loss',                       'EXPENSE',   'DEBIT',  true),
            ('5070', 'Purchase Price Variance',                    'EXPENSE',   'DEBIT',  true),
            ('5080', 'MAP Adjustment - FIFO Revaluation',          'EXPENSE',   'DEBIT',  true),
            -- ---------------------------------------------------------------
            -- 6100-6900: Operating Expenses
            -- ---------------------------------------------------------------
            ('6011', 'Salaries - Management',                      'EXPENSE',   'DEBIT',  true),
            ('6012', 'Salaries - Sales & Marketing',               'EXPENSE',   'DEBIT',  true),
            ('6013', 'Salaries - Warehouse & Logistics',           'EXPENSE',   'DEBIT',  true),
            ('6014', 'Salaries - IT & Engineering',                'EXPENSE',   'DEBIT',  true),
            ('6015', 'Salaries - Finance & Admin',                 'EXPENSE',   'DEBIT',  true),
            ('6016', 'End-of-Service Provision',                   'EXPENSE',   'DEBIT',  true),
            ('6017', 'Staff Medical Insurance',                    'EXPENSE',   'DEBIT',  true),
            ('6018', 'Staff Visa & Immigration',                   'EXPENSE',   'DEBIT',  true),
            ('6021', 'Office Rent',                                'EXPENSE',   'DEBIT',  true),
            ('6022', 'Warehouse Rent',                             'EXPENSE',   'DEBIT',  true),
            ('6023', 'Showroom Rent',                              'EXPENSE',   'DEBIT',  true),
            ('6031', 'Depreciation - Buildings',                   'EXPENSE',   'DEBIT',  true),
            ('6032', 'Depreciation - Machinery',                   'EXPENSE',   'DEBIT',  true),
            ('6033', 'Depreciation - Vehicles',                    'EXPENSE',   'DEBIT',  true),
            ('6034', 'Depreciation - Computers & IT',              'EXPENSE',   'DEBIT',  true),
            ('6035', 'Amortisation - Software',                    'EXPENSE',   'DEBIT',  true),
            ('6036', 'Amortisation - Trademarks',                  'EXPENSE',   'DEBIT',  true),
            ('6041', 'Electricity',                                'EXPENSE',   'DEBIT',  true),
            ('6042', 'Water & Sewerage',                           'EXPENSE',   'DEBIT',  true),
            ('6043', 'Telecom & Internet',                         'EXPENSE',   'DEBIT',  true),
            ('6051', 'Digital Marketing - Search Ads',             'EXPENSE',   'DEBIT',  true),
            ('6052', 'Digital Marketing - Social Media',           'EXPENSE',   'DEBIT',  true),
            ('6053', 'Exhibitions & Trade Shows',                  'EXPENSE',   'DEBIT',  true),
            ('6054', 'Public Relations',                           'EXPENSE',   'DEBIT',  true),
            ('6055', 'Branding & Design',                          'EXPENSE',   'DEBIT',  true),
            ('6061', 'Cloud Hosting & Infrastructure',             'EXPENSE',   'DEBIT',  true),
            ('6062', 'ERP & Business Software',                    'EXPENSE',   'DEBIT',  true),
            ('6063', 'Cybersecurity & Compliance Tools',           'EXPENSE',   'DEBIT',  true),
            ('6064', 'Domain & Certificates',                      'EXPENSE',   'DEBIT',  true),
            ('6071', 'Legal & Compliance Fees',                    'EXPENSE',   'DEBIT',  true),
            ('6072', 'Audit & Accounting Fees',                    'EXPENSE',   'DEBIT',  true),
            ('6073', 'Consulting Fees',                            'EXPENSE',   'DEBIT',  true),
            ('6081', 'Bank Charges - Local',                       'EXPENSE',   'DEBIT',  true),
            ('6082', 'Bank Charges - International Transfer',      'EXPENSE',   'DEBIT',  true),
            ('6083', 'FX Loss - Realised',                         'EXPENSE',   'DEBIT',  true),
            ('6084', 'FX Loss - Unrealised',                       'EXPENSE',   'DEBIT',  true),
            ('6091', 'Domestic Business Travel',                   'EXPENSE',   'DEBIT',  true),
            ('6092', 'International Business Travel',              'EXPENSE',   'DEBIT',  true),
            ('6093', 'Staff Entertainment',                        'EXPENSE',   'DEBIT',  true),
            ('6101', 'Property Insurance',                         'EXPENSE',   'DEBIT',  true),
            ('6102', 'Marine & Cargo Insurance',                   'EXPENSE',   'DEBIT',  true),
            ('6103', 'Liability Insurance',                        'EXPENSE',   'DEBIT',  true),
            ('6110', 'Office Supplies & Stationery',               'EXPENSE',   'DEBIT',  true),
            ('6120', 'Postage & Courier',                          'EXPENSE',   'DEBIT',  true),
            ('6130', 'Repairs & Maintenance',                      'EXPENSE',   'DEBIT',  true),
            ('6140', 'Security & Cleaning Services',               'EXPENSE',   'DEBIT',  true),
            ('6150', 'Training & Development',                     'EXPENSE',   'DEBIT',  true),
            ('6160', 'Penalties & Fines',                          'EXPENSE',   'DEBIT',  true),
            ('6170', 'Donations & Sponsorships',                   'EXPENSE',   'DEBIT',  true),
            ('6201', 'Corporate Tax - Current Year',               'EXPENSE',   'DEBIT',  true),
            ('6202', 'Deferred Tax Expense',                       'EXPENSE',   'DEBIT',  true),
            ('6211', 'FX Revaluation - Long-Term Items',           'EXPENSE',   'DEBIT',  true),
            ('6220', 'Impairment Loss - Goodwill',                 'EXPENSE',   'DEBIT',  true),
            ('6230', 'Provision for Bad Debts',                    'EXPENSE',   'DEBIT',  true)
        ON CONFLICT (account_code) DO NOTHING
    """))


def downgrade() -> None:
    # no-op — removing seeded accounts risks breaking FK references in
    # journal_entries and other accounting tables
    pass
