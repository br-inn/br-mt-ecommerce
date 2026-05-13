"""EP-ERP-06 — Finanzas: Schemas Pydantic para las 9 stories.

US-ERP-06-01: GlAccountOut, PostingPeriodOut
US-ERP-06-02: CostCenterOut, ProfitCenterOut
US-ERP-06-03: FinancialEntryOut, FinancialEntryCreate
US-ERP-06-04: VendorOpenItemOut, PaymentRunOut, PaymentRunCreate
US-ERP-06-05: StandardCostOut, StandardCostCreate, PriceVarianceOut
US-ERP-06-06: PlSummaryLine, BalanceSheetLine, TrialBalanceLine
US-ERP-06-07: PeriodCloseChecklistOut, TaxProvisionOut
US-ERP-06-08: JournalEntryControlOut, FxRevalResult
US-ERP-06-09: BudgetOut, BudgetCreate, BudgetVsActualLine, CashFlowOut, CopaLine
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

class _OrmBase(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# US-ERP-06-01 — Chart of Accounts
# ---------------------------------------------------------------------------

class GlAccountCreate(BaseModel):
    account_code: str
    account_name: str
    account_type: str  # ASSET|LIABILITY|EQUITY|REVENUE|EXPENSE|CONTRA
    parent_id: UUID | None = None
    is_reconciling: bool = False
    is_blocked: bool = False
    currency: str = "AED"


class GlAccountUpdate(BaseModel):
    account_name: str | None = None
    account_type: str | None = None
    is_reconciling: bool | None = None
    is_blocked: bool | None = None
    currency: str | None = None


class GlAccountOut(_OrmBase):
    id: UUID
    account_code: str
    account_name: str
    account_type: str
    parent_id: UUID | None
    is_reconciling: bool
    is_blocked: bool
    currency: str
    created_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-06-01 — Posting Periods
# ---------------------------------------------------------------------------

class PostingPeriodCreate(BaseModel):
    fiscal_year: int
    period_num: int
    period_name: str | None = None
    date_from: date
    date_to: date
    status: str = "open"


class PostingPeriodOut(_OrmBase):
    id: UUID
    fiscal_year: int
    period_num: int
    period_name: str | None
    date_from: date
    date_to: date
    status: str
    closed_at: datetime | None
    closed_by: UUID | None


# ---------------------------------------------------------------------------
# US-ERP-06-02 — Cost Centers
# ---------------------------------------------------------------------------

class CostCenterCreate(BaseModel):
    cc_code: str
    cc_name: str
    parent_id: UUID | None = None
    cc_type: str | None = None
    responsible_id: UUID | None = None
    valid_from: date | None = None
    valid_to: date | None = None


class CostCenterOut(_OrmBase):
    id: UUID
    cc_code: str
    cc_name: str
    parent_id: UUID | None
    cc_type: str | None
    responsible_id: UUID | None
    valid_from: date
    valid_to: date | None
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-06-02 — Profit Centers
# ---------------------------------------------------------------------------

class ProfitCenterCreate(BaseModel):
    pc_code: str
    pc_name: str
    business_area: str  # B2C|B2B|INTERNAL
    responsible_id: UUID | None = None


class ProfitCenterOut(_OrmBase):
    id: UUID
    pc_code: str
    pc_name: str
    business_area: str
    responsible_id: UUID | None
    is_active: bool
    created_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-06-03 — Universal Journal
# ---------------------------------------------------------------------------

class FinancialEntryCreate(BaseModel):
    entry_number: str
    journal_date: date
    posting_period: int
    fiscal_year: int
    entry_type: str = "MANUAL"
    source_module: str | None = None
    source_document: str | None = None
    source_document_id: UUID | None = None
    gl_account_id: UUID
    cost_center_id: UUID | None = None
    profit_center_id: UUID | None = None
    debit_amount: Decimal = Decimal("0")
    credit_amount: Decimal = Decimal("0")
    currency_code: str = "AED"
    amount_local: Decimal | None = None
    fx_rate: Decimal | None = Decimal("1")
    description: str | None = None
    reference: str | None = None


class FinancialEntryOut(_OrmBase):
    id: UUID
    entry_number: str
    journal_date: date
    posting_period: int
    fiscal_year: int
    entry_type: str
    source_module: str | None
    source_document: str | None
    source_document_id: UUID | None
    gl_account_id: UUID
    cost_center_id: UUID | None
    profit_center_id: UUID | None
    debit_amount: Decimal
    credit_amount: Decimal
    currency_code: str
    amount_local: Decimal | None
    fx_rate: Decimal | None
    description: str | None
    reference: str | None
    preparer_id: UUID | None
    reviewer_id: UUID | None
    approver_id: UUID | None
    is_reversed: bool
    reversal_entry_id: UUID | None
    created_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-06-04 — AP Aging + Payment Run
# ---------------------------------------------------------------------------

class VendorOpenItemCreate(BaseModel):
    vendor_id: str
    po_id: UUID | None = None
    invoice_ref: str | None = None
    document_type: str = "vendor_invoice"
    amount: Decimal
    currency: str = "AED"
    due_date: date | None = None


class VendorOpenItemOut(_OrmBase):
    id: UUID
    vendor_id: str
    po_id: UUID | None
    invoice_ref: str | None
    document_type: str
    amount: Decimal
    currency: str
    due_date: date | None
    status: str
    payment_block: bool
    created_at: datetime


class ApAgingBucket(BaseModel):
    vendor_id: str
    current: Decimal = Decimal("0")
    days_1_30: Decimal = Decimal("0")
    days_31_60: Decimal = Decimal("0")
    days_61_90: Decimal = Decimal("0")
    days_90_plus: Decimal = Decimal("0")
    total: Decimal = Decimal("0")


class ApAgingOut(BaseModel):
    as_of_date: date
    buckets: list[ApAgingBucket]


class PaymentRunCreate(BaseModel):
    run_date: date
    payment_method: str | None = None
    currency: str = "AED"
    vendor_ids: list[str] | None = None  # None = todos los vencidos
    cutoff_date: date | None = None


class PaymentRunOut(_OrmBase):
    id: UUID
    run_number: str
    run_date: date
    payment_method: str | None
    total_amount: Decimal | None
    currency: str
    status: str
    created_by: UUID | None
    approved_by: UUID | None
    created_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-06-05 — Standard Cost + Variance
# ---------------------------------------------------------------------------

class StandardCostCreate(BaseModel):
    product_sku: str
    fiscal_year: int
    standard_cost: Decimal
    currency: str = "AED"
    cost_type: str = "standard"
    valid_from: date | None = None
    valid_to: date | None = None


class StandardCostOut(_OrmBase):
    id: UUID
    product_sku: str
    fiscal_year: int
    standard_cost: Decimal
    currency: str
    cost_type: str
    valid_from: date
    valid_to: date | None
    created_by: UUID | None
    created_at: datetime


class PriceVarianceOut(_OrmBase):
    id: UUID
    po_line_id: UUID | None
    product_sku: str
    standard_cost: Decimal
    actual_cost: Decimal
    variance_amount: Decimal
    variance_pct: Decimal | None
    period: int | None
    fiscal_year: int | None
    created_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-06-06 — P&L + Balance Sheet + Trial Balance
# ---------------------------------------------------------------------------

class PlLineOut(BaseModel):
    fiscal_year: int
    posting_period: int
    account_code: str
    account_name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    net_amount: Decimal


class PlSummaryOut(BaseModel):
    fiscal_year: int
    period_from: int
    period_to: int
    revenue_total: Decimal
    expense_total: Decimal
    net_income: Decimal
    lines: list[PlLineOut]


class BalanceSheetLineOut(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    balance: Decimal


class BalanceSheetOut(BaseModel):
    as_of_period: int
    fiscal_year: int
    total_assets: Decimal
    total_liabilities: Decimal
    total_equity: Decimal
    lines: list[BalanceSheetLineOut]


class TrialBalanceLineOut(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    total_debit: Decimal
    total_credit: Decimal
    balance: Decimal


class TrialBalanceOut(BaseModel):
    fiscal_year: int
    period: int
    lines: list[TrialBalanceLineOut]
    total_debit: Decimal
    total_credit: Decimal


# ---------------------------------------------------------------------------
# US-ERP-06-07 — Period Close + Tax Provisions
# ---------------------------------------------------------------------------

class PeriodCloseChecklistOut(_OrmBase):
    id: UUID
    fiscal_year: int | None
    period_num: int | None
    checklist_items: list[Any]
    status: str
    started_at: datetime | None
    completed_at: datetime | None
    completed_by: UUID | None


class ChecklistItemUpdate(BaseModel):
    item_index: int
    completed: bool
    item_name: str | None = None  # para marcar por nombre


class TaxProvisionOut(_OrmBase):
    id: UUID
    provision_type: str | None
    fiscal_year: int | None
    period_num: int | None
    taxable_base: Decimal | None
    tax_rate: Decimal | None
    provision_amount: Decimal | None
    status: str
    gl_entry_id: UUID | None
    created_at: datetime


class CitProvisionResult(BaseModel):
    fiscal_year: int
    taxable_base: Decimal
    tax_rate: Decimal = Decimal("0.09")
    cit_exempt_threshold: Decimal = Decimal("375000")
    provision_amount: Decimal
    provision_id: UUID | None = None
    message: str


# ---------------------------------------------------------------------------
# US-ERP-06-08 — FX Revaluation + SoD Controls
# ---------------------------------------------------------------------------

class FxRevalResult(BaseModel):
    fiscal_year: int
    period: int
    accounts_revalued: int
    total_fx_gain: Decimal
    total_fx_loss: Decimal
    entries_created: int


class JournalEntryControlCreate(BaseModel):
    user_id: UUID
    control_type: str  # PREPARER|REVIEWER|APPROVER
    gl_account_code: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None


class JournalEntryControlOut(_OrmBase):
    id: UUID
    user_id: UUID
    control_type: str
    gl_account_code: str | None
    effective_from: date
    effective_to: date | None


class EntryReviewApproveOut(BaseModel):
    entry_id: UUID
    action: str  # reviewed|approved
    by_user: UUID
    at: datetime


# ---------------------------------------------------------------------------
# US-ERP-06-09 — CO-PA + Budget vs Actual + Cash Flow
# ---------------------------------------------------------------------------

class CopaLineOut(BaseModel):
    profit_center_code: str
    profit_center_name: str
    revenue: Decimal
    cogs: Decimal
    gross_margin: Decimal
    gross_margin_pct: Decimal | None
    opex: Decimal
    ebit: Decimal


class CopaOut(BaseModel):
    fiscal_year: int
    profit_center: str | None
    lines: list[CopaLineOut]


class BudgetCreate(BaseModel):
    fiscal_year: int
    period_num: int
    gl_account_id: UUID
    profit_center_id: UUID | None = None
    budget_amount: Decimal
    currency: str = "AED"


class BudgetOut(_OrmBase):
    id: UUID
    fiscal_year: int
    period_num: int
    gl_account_id: UUID
    profit_center_id: UUID | None
    budget_amount: Decimal
    currency: str


class BudgetVsActualLine(BaseModel):
    account_code: str
    account_name: str
    account_type: str
    profit_center_code: str | None
    budget: Decimal
    actual: Decimal
    variance: Decimal
    variance_pct: Decimal | None


class BudgetVsActualOut(BaseModel):
    fiscal_year: int
    period: int
    lines: list[BudgetVsActualLine]
    total_budget: Decimal
    total_actual: Decimal
    total_variance: Decimal


class CashFlowOut(BaseModel):
    fiscal_year: int
    period_from: int
    period_to: int
    operating_inflows: Decimal   # cobros clientes (1100)
    operating_outflows: Decimal  # pagos proveedores (2100)
    net_operating: Decimal
    net_investing: Decimal = Decimal("0")   # stub
    net_financing: Decimal = Decimal("0")   # stub
    net_change: Decimal
    opening_cash: Decimal = Decimal("0")
    closing_cash: Decimal
