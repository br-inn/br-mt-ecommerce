/**
 * EP-ERP-06 — Finanzas: API client
 *
 * Cubre todos los endpoints de /api/v1/finance
 */

import { apiClient } from "@/lib/api/client";

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
    apiClient.get<GlAccount[]>("/finance/accounts", { params }),

  createAccount: (data: Partial<GlAccount>) =>
    apiClient.post<GlAccount>("/finance/accounts", data),

  updateAccount: (id: string, data: Partial<GlAccount>) =>
    apiClient.patch<GlAccount>(`/finance/accounts/${id}`, data),

  // Posting Periods
  listPostingPeriods: (params?: { fiscal_year?: number; status?: string }) =>
    apiClient.get<PostingPeriod[]>("/finance/posting-periods", { params }),

  createPostingPeriod: (data: Partial<PostingPeriod>) =>
    apiClient.post<PostingPeriod>("/finance/posting-periods", data),

  closePeriod: (id: string) =>
    apiClient.post<PostingPeriod>(`/finance/posting-periods/${id}/close`),

  // Cost Centers
  listCostCenters: () =>
    apiClient.get<CostCenter[]>("/finance/cost-centers"),

  // Profit Centers
  listProfitCenters: () =>
    apiClient.get<ProfitCenter[]>("/finance/profit-centers"),

  // Financial Entries
  listEntries: (params?: {
    gl_account?: string;
    period?: number;
    fiscal_year?: number;
    source_module?: string;
    limit?: number;
    offset?: number;
  }) => apiClient.get<FinancialEntry[]>("/finance/entries", { params }),

  createEntry: (data: FinancialEntryCreate) =>
    apiClient.post<FinancialEntry>("/finance/entries", data),

  reverseEntry: (id: string) =>
    apiClient.post<FinancialEntry>(`/finance/entries/${id}/reverse`),

  reviewEntry: (id: string) =>
    apiClient.post(`/finance/entries/${id}/review`),

  approveEntry: (id: string) =>
    apiClient.post(`/finance/entries/${id}/approve`),

  // AP Aging
  getApAging: (params?: { as_of_date?: string; vendor_id?: string }) =>
    apiClient.get<ApAgingOut>("/finance/ap-aging", { params }),

  // Payment Runs
  createPaymentRun: (data: {
    run_date: string;
    payment_method?: string;
    currency?: string;
    vendor_ids?: string[];
    cutoff_date?: string;
  }) => apiClient.post<PaymentRun>("/finance/payment-runs", data),

  approvePaymentRun: (id: string) =>
    apiClient.post<PaymentRun>(`/finance/payment-runs/${id}/approve`),

  executePaymentRun: (id: string) =>
    apiClient.post<PaymentRun>(`/finance/payment-runs/${id}/execute`),

  // Standard Costs
  listStandardCosts: (params?: { sku?: string; fiscal_year?: number }) =>
    apiClient.get<StandardCost[]>("/finance/standard-costs", { params }),

  createStandardCost: (data: Partial<StandardCost>) =>
    apiClient.post<StandardCost>("/finance/standard-costs", data),

  // P&L
  getPl: (params: { fiscal_year: number; period_from?: number; period_to?: number }) =>
    apiClient.get<PlSummaryOut>("/finance/pl", { params }),

  // Balance Sheet
  getBalanceSheet: (params: { fiscal_year: number; as_of_period?: number }) =>
    apiClient.get<BalanceSheetOut>("/finance/balance-sheet", { params }),

  // Trial Balance
  getTrialBalance: (params: { fiscal_year: number; period: number }) =>
    apiClient.get<TrialBalanceOut>("/finance/trial-balance", { params }),

  // Period Close
  startPeriodClose: (fiscal_year: number, period_num: number) =>
    apiClient.post<PeriodCloseChecklist>(`/finance/period-close/${fiscal_year}/${period_num}`),

  updateChecklistItem: (id: string, data: { item_index: number; completed: boolean; item_name?: string }) =>
    apiClient.patch<PeriodCloseChecklist>(`/finance/period-close/${id}/item`, data),

  closePeriodChecklist: (id: string) =>
    apiClient.post<PeriodCloseChecklist>(`/finance/period-close/${id}/close`),

  // UAE CIT
  calculateCit: (fiscal_year: number) =>
    apiClient.post<CitProvisionResult>(`/finance/cit-provision/${fiscal_year}`),

  // FX Revaluation
  runFxRevaluation: (fiscal_year: number, period: number) =>
    apiClient.post<FxRevalResult>(`/finance/fx-revaluation/${fiscal_year}/${period}`),

  // Budgets
  listBudgets: (params?: { fiscal_year?: number; period_num?: number }) =>
    apiClient.get<Budget[]>("/finance/budgets", { params }),

  createBudget: (data: Partial<Budget>) =>
    apiClient.post<Budget>("/finance/budgets", data),

  getBudgetVsActual: (params: { fiscal_year: number; period: number }) =>
    apiClient.get<BudgetVsActualOut>("/finance/budget-vs-actual", { params }),

  // CO-PA
  getCopa: (params: { fiscal_year: number; profit_center?: string }) =>
    apiClient.get<CopaOut>("/finance/copa", { params }),
};
