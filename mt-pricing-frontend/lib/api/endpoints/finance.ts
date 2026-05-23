/**
 * EP-ERP-06 — Finanzas: API client
 *
 * Cubre todos los endpoints de /api/v1/finance
 */

import { authedFetch } from "@/lib/api/client";

function qs(params: Record<string, unknown> | undefined): string {
  if (!params) return "";
  const pairs = Object.entries(params).filter(([, v]) => v !== undefined && v !== null);
  if (pairs.length === 0) return "";
  return "?" + pairs.map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(String(v))}`).join("&");
}

const BASE = "/api/v1/finance";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface GlAccount {
  id: string;
  account_code: string;
  account_name: string;
  account_type: "ASSET" | "LIABILITY" | "EQUITY" | "REVENUE" | "EXPENSE" | "CONTRA";
  parent_id: string | null;
  is_reconciling: boolean;
  is_blocked: boolean;
  currency: string;
  created_at: string;
}

export interface PostingPeriod {
  id: string;
  fiscal_year: number;
  period_num: number;
  period_name: string | null;
  date_from: string;
  date_to: string;
  status: "open" | "closed" | "locked";
  closed_at: string | null;
  closed_by: string | null;
}

export interface CostCenter {
  id: string;
  cc_code: string;
  cc_name: string;
  parent_id: string | null;
  cc_type: string | null;
  responsible_id: string | null;
  valid_from: string;
  valid_to: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ProfitCenter {
  id: string;
  pc_code: string;
  pc_name: string;
  business_area: "B2C" | "B2B" | "INTERNAL";
  responsible_id: string | null;
  is_active: boolean;
  created_at: string;
}

export interface FinancialEntry {
  id: string;
  entry_number: string;
  journal_date: string;
  posting_period: number;
  fiscal_year: number;
  entry_type: "MANUAL" | "SYSTEM" | "REVERSAL" | "ACCRUAL" | "FX_REVAL";
  source_module: string | null;
  source_document: string | null;
  source_document_id: string | null;
  gl_account_id: string;
  cost_center_id: string | null;
  profit_center_id: string | null;
  debit_amount: string;
  credit_amount: string;
  currency_code: string;
  amount_local: string | null;
  fx_rate: string | null;
  description: string | null;
  reference: string | null;
  preparer_id: string | null;
  reviewer_id: string | null;
  approver_id: string | null;
  is_reversed: boolean;
  reversal_entry_id: string | null;
  created_at: string;
}

export interface FinancialEntryCreate {
  entry_number: string;
  journal_date: string;
  posting_period: number;
  fiscal_year: number;
  entry_type?: string;
  gl_account_id: string;
  debit_amount: string;
  credit_amount: string;
  currency_code?: string;
  description?: string;
  cost_center_id?: string;
  profit_center_id?: string;
}

export interface ApAgingBucket {
  vendor_id: string;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_90_plus: string;
  total: string;
}

export interface ApAgingOut {
  as_of_date: string;
  buckets: ApAgingBucket[];
}

export interface PaymentRun {
  id: string;
  run_number: string;
  run_date: string;
  payment_method: string | null;
  total_amount: string | null;
  currency: string;
  status: "proposed" | "approved" | "executed" | "cancelled";
  created_by: string | null;
  approved_by: string | null;
  created_at: string;
}

export interface PlSummaryOut {
  fiscal_year: number;
  period_from: number;
  period_to: number;
  revenue_total: string;
  expense_total: string;
  net_income: string;
  lines: PlLine[];
}

export interface PlLine {
  fiscal_year: number;
  posting_period: number;
  account_code: string;
  account_name: string;
  account_type: string;
  total_debit: string;
  total_credit: string;
  net_amount: string;
}

export interface BalanceSheetOut {
  as_of_period: number;
  fiscal_year: number;
  total_assets: string;
  total_liabilities: string;
  total_equity: string;
  lines: BalanceSheetLine[];
}

export interface BalanceSheetLine {
  account_code: string;
  account_name: string;
  account_type: string;
  balance: string;
}

export interface TrialBalanceOut {
  fiscal_year: number;
  period: number;
  lines: TrialBalanceLine[];
  total_debit: string;
  total_credit: string;
}

export interface TrialBalanceLine {
  account_code: string;
  account_name: string;
  account_type: string;
  total_debit: string;
  total_credit: string;
  balance: string;
}

export interface PeriodCloseChecklist {
  id: string;
  fiscal_year: number | null;
  period_num: number | null;
  checklist_items: (string | { name: string; completed: boolean })[];
  status: "open" | "in_progress" | "closed";
  started_at: string | null;
  completed_at: string | null;
  completed_by: string | null;
}

export interface StandardCost {
  id: string;
  product_sku: string;
  fiscal_year: number;
  standard_cost: string;
  currency: string;
  cost_type: string;
  valid_from: string;
  valid_to: string | null;
  created_by: string | null;
  created_at: string;
}

export interface Budget {
  id: string;
  fiscal_year: number;
  period_num: number;
  gl_account_id: string;
  profit_center_id: string | null;
  budget_amount: string;
  currency: string;
}

export interface BudgetVsActualOut {
  fiscal_year: number;
  period: number;
  lines: BudgetVsActualLine[];
  total_budget: string;
  total_actual: string;
  total_variance: string;
}

export interface BudgetVsActualLine {
  account_code: string;
  account_name: string;
  account_type: string;
  profit_center_code: string | null;
  budget: string;
  actual: string;
  variance: string;
  variance_pct: string | null;
}

export interface CopaOut {
  fiscal_year: number;
  profit_center: string | null;
  lines: CopaLine[];
}

export interface CopaLine {
  profit_center_code: string;
  profit_center_name: string;
  revenue: string;
  cogs: string;
  gross_margin: string;
  gross_margin_pct: string | null;
  opex: string;
  ebit: string;
}

export interface CitProvisionResult {
  fiscal_year: number;
  taxable_base: string;
  tax_rate: string;
  cit_exempt_threshold: string;
  provision_amount: string;
  provision_id: string | null;
  message: string;
}

export interface FxRevalResult {
  fiscal_year: number;
  period: number;
  accounts_revalued: number;
  total_fx_gain: string;
  total_fx_loss: string;
  entries_created: number;
}

// ---------------------------------------------------------------------------
// API functions
// ---------------------------------------------------------------------------

export const financeApi = {
  // GL Accounts
  listAccounts: (params?: { account_type?: string; blocked?: boolean }) =>
    authedFetch<GlAccount[]>(`${BASE}/accounts${qs(params as Record<string, unknown>)}`),

  createAccount: (data: Partial<GlAccount>) =>
    authedFetch<GlAccount>(`${BASE}/accounts`, { method: "POST", body: JSON.stringify(data) }),

  updateAccount: (id: string, data: Partial<GlAccount>) =>
    authedFetch<GlAccount>(`${BASE}/accounts/${id}`, { method: "PATCH", body: JSON.stringify(data) }),

  // Posting Periods
  listPostingPeriods: (params?: { fiscal_year?: number; status?: string }) =>
    authedFetch<PostingPeriod[]>(`${BASE}/posting-periods${qs(params as Record<string, unknown>)}`),

  createPostingPeriod: (data: Partial<PostingPeriod>) =>
    authedFetch<PostingPeriod>(`${BASE}/posting-periods`, { method: "POST", body: JSON.stringify(data) }),

  closePeriod: (id: string) =>
    authedFetch<PostingPeriod>(`${BASE}/posting-periods/${id}/close`, { method: "POST" }),

  // Cost Centers
  listCostCenters: () =>
    authedFetch<CostCenter[]>(`${BASE}/cost-centers`),

  // Profit Centers
  listProfitCenters: () =>
    authedFetch<ProfitCenter[]>(`${BASE}/profit-centers`),

  // Financial Entries
  listEntries: (params?: {
    gl_account?: string;
    period?: number;
    fiscal_year?: number;
    source_module?: string;
    limit?: number;
    offset?: number;
  }) => authedFetch<FinancialEntry[]>(`${BASE}/entries${qs(params as Record<string, unknown>)}`),

  createEntry: (data: FinancialEntryCreate) =>
    authedFetch<FinancialEntry>(`${BASE}/entries`, { method: "POST", body: JSON.stringify(data) }),

  reverseEntry: (id: string) =>
    authedFetch<FinancialEntry>(`${BASE}/entries/${id}/reverse`, { method: "POST" }),

  reviewEntry: (id: string) =>
    authedFetch<void>(`${BASE}/entries/${id}/review`, { method: "POST" }),

  approveEntry: (id: string) =>
    authedFetch<void>(`${BASE}/entries/${id}/approve`, { method: "POST" }),

  // AP Aging
  getApAging: (params?: { as_of_date?: string; vendor_id?: string }) =>
    authedFetch<ApAgingOut>(`${BASE}/ap-aging${qs(params as Record<string, unknown>)}`),

  // Payment Runs
  createPaymentRun: (data: {
    run_date: string;
    payment_method?: string;
    currency?: string;
    vendor_ids?: string[];
    cutoff_date?: string;
  }) => authedFetch<PaymentRun>(`${BASE}/payment-runs`, { method: "POST", body: JSON.stringify(data) }),

  approvePaymentRun: (id: string) =>
    authedFetch<PaymentRun>(`${BASE}/payment-runs/${id}/approve`, { method: "POST" }),

  executePaymentRun: (id: string) =>
    authedFetch<PaymentRun>(`${BASE}/payment-runs/${id}/execute`, { method: "POST" }),

  // Standard Costs
  listStandardCosts: (params?: { sku?: string; fiscal_year?: number }) =>
    authedFetch<StandardCost[]>(`${BASE}/standard-costs${qs(params as Record<string, unknown>)}`),

  createStandardCost: (data: Partial<StandardCost>) =>
    authedFetch<StandardCost>(`${BASE}/standard-costs`, { method: "POST", body: JSON.stringify(data) }),

  // P&L
  getPl: (params: { fiscal_year: number; period_from?: number; period_to?: number }) =>
    authedFetch<PlSummaryOut>(`${BASE}/pl${qs(params as Record<string, unknown>)}`),

  // Balance Sheet
  getBalanceSheet: (params: { fiscal_year: number; as_of_period?: number }) =>
    authedFetch<BalanceSheetOut>(`${BASE}/balance-sheet${qs(params as Record<string, unknown>)}`),

  // Trial Balance
  getTrialBalance: (params: { fiscal_year: number; period: number }) =>
    authedFetch<TrialBalanceOut>(`${BASE}/trial-balance${qs(params as Record<string, unknown>)}`),

  // Period Close
  startPeriodClose: (fiscal_year: number, period_num: number) =>
    authedFetch<PeriodCloseChecklist>(`${BASE}/period-close/${fiscal_year}/${period_num}`, { method: "POST" }),

  updateChecklistItem: (id: string, data: { item_index: number; completed: boolean; item_name?: string }) =>
    authedFetch<PeriodCloseChecklist>(`${BASE}/period-close/${id}/item`, { method: "PATCH", body: JSON.stringify(data) }),

  closePeriodChecklist: (id: string) =>
    authedFetch<PeriodCloseChecklist>(`${BASE}/period-close/${id}/close`, { method: "POST" }),

  // UAE CIT
  calculateCit: (fiscal_year: number) =>
    authedFetch<CitProvisionResult>(`${BASE}/cit-provision/${fiscal_year}`, { method: "POST" }),

  // FX Revaluation
  runFxRevaluation: (fiscal_year: number, period: number) =>
    authedFetch<FxRevalResult>(`${BASE}/fx-revaluation/${fiscal_year}/${period}`, { method: "POST" }),

  // Budgets
  listBudgets: (params?: { fiscal_year?: number; period_num?: number }) =>
    authedFetch<Budget[]>(`${BASE}/budgets${qs(params as Record<string, unknown>)}`),

  createBudget: (data: Partial<Budget>) =>
    authedFetch<Budget>(`${BASE}/budgets`, { method: "POST", body: JSON.stringify(data) }),

  getBudgetVsActual: (params: { fiscal_year: number; period: number }) =>
    authedFetch<BudgetVsActualOut>(`${BASE}/budget-vs-actual${qs(params as Record<string, unknown>)}`),

  // CO-PA
  getCopa: (params: { fiscal_year: number; profit_center?: string }) =>
    authedFetch<CopaOut>(`${BASE}/copa${qs(params as Record<string, unknown>)}`),
};
