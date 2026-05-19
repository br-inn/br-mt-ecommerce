"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type PRStatus =
  | "draft"
  | "pending_approval"
  | "approved"
  | "rejected"
  | "cancelled"
  | "converted_to_po";

export interface PurchaseRequisitionRead {
  id: string;
  pr_number: string;
  requester_id: string;
  product_sku: string | null;
  qty: string;
  uom: string;
  required_date: string | null;
  cost_center_id: string | null;
  suggested_vendor_id: string | null;
  estimated_amount: string | null;
  status: PRStatus;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface PRCreatePayload {
  product_sku?: string | null;
  qty: string;
  uom?: string;
  required_date?: string | null;
  cost_center_id?: string | null;
  suggested_vendor_id?: string | null;
  estimated_amount?: string | null;
  notes?: string | null;
}

export interface PRFilters {
  status?: PRStatus | "" | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
}

export interface ApprovalRuleRead {
  id: string;
  document_type: string;
  min_amount: string;
  max_amount: string | null;
  category_id: string | null;
  approver_role: string | null;
  approver_user_id: string | null;
  timeout_hours: number;
  priority: number;
  is_active: boolean;
  created_at: string;
}

export interface ApprovalRuleCreatePayload {
  document_type?: string;
  min_amount?: string;
  max_amount?: string | null;
  category_id?: string | null;
  approver_role?: string | null;
  approver_user_id?: string | null;
  timeout_hours?: number;
  priority?: number;
  is_active?: boolean;
}

export interface VendorConditionRead {
  id: string;
  vendor_id: string;
  product_sku: string;
  price: string;
  uom: string;
  moq: number;
  lead_time_days: number | null;
  valid_from: string;
  valid_to: string | null;
  currency: string;
  is_active: boolean;
  created_at: string;
}

export interface VendorConditionCreatePayload {
  vendor_id: string;
  product_sku: string;
  price: string;
  uom?: string;
  moq?: number;
  lead_time_days?: number | null;
  valid_from?: string | null;
  valid_to?: string | null;
  currency?: string;
  is_active?: boolean;
}

export interface VendorConditionUpdatePayload {
  price?: string;
  uom?: string;
  moq?: number;
  lead_time_days?: number | null;
  valid_to?: string | null;
  currency?: string;
  is_active?: boolean;
}

// ---------------------------------------------------------------------------
// Internal helpers
// ---------------------------------------------------------------------------

export class ProcurementApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ProcurementApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  const res = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      /* noop */
    }
    throw new ProcurementApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    search.set(k, String(v));
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

const BASE = "/api/v1/procurement";

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

export const procurementApi = {
  // --- Purchase Requisitions -----------------------------------------------
  listRequisitions: (filters: PRFilters = {}): Promise<PurchaseRequisitionRead[]> =>
    authedFetch<PurchaseRequisitionRead[]>(
      `${BASE}/requisitions${buildQuery({
        status: filters.status,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
      })}`,
    ),

  getRequisition: (id: string): Promise<PurchaseRequisitionRead> =>
    authedFetch<PurchaseRequisitionRead>(`${BASE}/requisitions/${id}`),

  createRequisition: (payload: PRCreatePayload): Promise<PurchaseRequisitionRead> =>
    authedFetch<PurchaseRequisitionRead>(`${BASE}/requisitions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  submitRequisition: (id: string): Promise<PurchaseRequisitionRead> =>
    authedFetch<PurchaseRequisitionRead>(`${BASE}/requisitions/${id}/submit`, {
      method: "PATCH",
    }),

  approveRequisition: (id: string): Promise<PurchaseRequisitionRead> =>
    authedFetch<PurchaseRequisitionRead>(`${BASE}/requisitions/${id}/approve`, {
      method: "PATCH",
    }),

  rejectRequisition: (id: string, reason: string): Promise<PurchaseRequisitionRead> =>
    authedFetch<PurchaseRequisitionRead>(`${BASE}/requisitions/${id}/reject`, {
      method: "PATCH",
      body: JSON.stringify({ reason }),
    }),

  cancelRequisition: (id: string): Promise<PurchaseRequisitionRead> =>
    authedFetch<PurchaseRequisitionRead>(`${BASE}/requisitions/${id}/cancel`, {
      method: "PATCH",
    }),

  // --- Approval Rules -------------------------------------------------------
  listApprovalRules: (): Promise<ApprovalRuleRead[]> =>
    authedFetch<ApprovalRuleRead[]>(`${BASE}/approval-rules`),

  createApprovalRule: (payload: ApprovalRuleCreatePayload): Promise<ApprovalRuleRead> =>
    authedFetch<ApprovalRuleRead>(`${BASE}/approval-rules`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateApprovalRule: (
    id: string,
    payload: Partial<ApprovalRuleCreatePayload>,
  ): Promise<ApprovalRuleRead> =>
    authedFetch<ApprovalRuleRead>(`${BASE}/approval-rules/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  // --- Vendor Conditions (PIR) ----------------------------------------------
  listVendorConditions: (params: {
    vendor_id?: string;
    product_sku?: string;
    active_only?: boolean;
  } = {}): Promise<VendorConditionRead[]> =>
    authedFetch<VendorConditionRead[]>(
      `${BASE}/vendor-conditions${buildQuery(params)}`,
    ),

  createVendorCondition: (
    payload: VendorConditionCreatePayload,
  ): Promise<VendorConditionRead> =>
    authedFetch<VendorConditionRead>(`${BASE}/vendor-conditions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateVendorCondition: (
    id: string,
    payload: VendorConditionUpdatePayload,
  ): Promise<VendorConditionRead> =>
    authedFetch<VendorConditionRead>(`${BASE}/vendor-conditions/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
};

// ---------------------------------------------------------------------------
// US-ERP-03-04 — Vendor Invoices + 3-way match
// ---------------------------------------------------------------------------

export type VendorInvoiceStatus =
  | "pending"
  | "matched"
  | "tolerance_ok"
  | "blocked"
  | "approved"
  | "paid";

export interface VendorInvoiceRead {
  id: string;
  invoice_number: string;
  vendor_id: string;
  po_id: string;
  gr_id: string | null;
  invoice_date: string;
  total_amount: string;
  currency: string;
  status: VendorInvoiceStatus;
  payment_block: boolean;
  match_details: Record<string, unknown> | null;
  created_at: string;
}

export interface VendorInvoiceCreatePayload {
  invoice_number: string;
  vendor_id: string;
  po_id: string;
  gr_id?: string | null;
  invoice_date: string;
  total_amount: string;
  currency?: string;
}

export interface InvoiceToleranceRead {
  id: string;
  document_type: string;
  vendor_category: string | null;
  tolerance_key: string;
  absolute_limit: string | null;
  pct_limit: string | null;
  currency: string;
  is_active: boolean;
}

export interface VendorInvoiceFilters {
  vendor_id?: string;
  status?: VendorInvoiceStatus;
  limit?: number;
}

export const vendorInvoicesApi = {
  list: (filters: VendorInvoiceFilters = {}): Promise<VendorInvoiceRead[]> =>
    authedFetch<VendorInvoiceRead[]>(
      `${BASE}/invoices${buildQuery(filters as Record<string, string | number | boolean | undefined | null>)}`,
    ),

  create: (payload: VendorInvoiceCreatePayload): Promise<VendorInvoiceRead> =>
    authedFetch<VendorInvoiceRead>(`${BASE}/invoices`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  match: (id: string): Promise<VendorInvoiceRead> =>
    authedFetch<VendorInvoiceRead>(`${BASE}/invoices/${id}/match`, {
      method: "POST",
    }),

  releaseBlock: (id: string, reason: string): Promise<VendorInvoiceRead> =>
    authedFetch<VendorInvoiceRead>(`${BASE}/invoices/${id}/release-block`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
};

export const invoiceTolerancesApi = {
  list: (activeOnly = true): Promise<InvoiceToleranceRead[]> =>
    authedFetch<InvoiceToleranceRead[]>(
      `${BASE}/invoice-tolerances${buildQuery({ active_only: activeOnly })}`,
    ),

  create: (payload: Partial<InvoiceToleranceRead>): Promise<InvoiceToleranceRead> =>
    authedFetch<InvoiceToleranceRead>(`${BASE}/invoice-tolerances`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  update: (id: string, payload: Partial<InvoiceToleranceRead>): Promise<InvoiceToleranceRead> =>
    authedFetch<InvoiceToleranceRead>(`${BASE}/invoice-tolerances/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
};

// ---------------------------------------------------------------------------
// US-ERP-03-05 — Source List + RFQ
// ---------------------------------------------------------------------------

export interface SourceListRead {
  id: string;
  product_sku: string;
  vendor_id: string;
  vendor_name: string | null;
  is_preferred: boolean;
  is_blocked: boolean;
  valid_from: string;
  valid_to: string | null;
  fixed_source: boolean;
  notes: string | null;
}

export type RfqStatus = "draft" | "sent" | "responses_received" | "awarded" | "cancelled";

export interface RfqRead {
  id: string;
  rfq_number: string;
  pr_id: string | null;
  status: RfqStatus;
  deadline: string | null;
  notes: string | null;
  created_at: string;
  created_by: string;
}

export interface RfqResponseRead {
  id: string;
  rfq_id: string;
  vendor_id: string;
  unit_price: string | null;
  currency: string;
  lead_time_days: number | null;
  valid_until: string | null;
  notes: string | null;
  responded_at: string | null;
}

export interface RfqComparisonItem {
  vendor_id: string;
  unit_price: string | null;
  currency: string;
  lead_time_days: number | null;
  score: number | null;
}

export interface RfqComparisonOut {
  rfq_id: string;
  rfq_number: string;
  items: RfqComparisonItem[];
}

export const sourceListApi = {
  list: (params: { product_sku?: string; include_blocked?: boolean } = {}): Promise<SourceListRead[]> =>
    authedFetch<SourceListRead[]>(
      `${BASE}/source-list${buildQuery(params as Record<string, string | number | boolean | undefined | null>)}`,
    ),

  create: (payload: Partial<SourceListRead>): Promise<SourceListRead> =>
    authedFetch<SourceListRead>(`${BASE}/source-list`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  update: (id: string, payload: Partial<SourceListRead>): Promise<SourceListRead> =>
    authedFetch<SourceListRead>(`${BASE}/source-list/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  delete: (id: string): Promise<void> =>
    authedFetch<void>(`${BASE}/source-list/${id}`, { method: "DELETE" }),
};

export const rfqApi = {
  list: (params: { status?: RfqStatus; limit?: number } = {}): Promise<RfqRead[]> =>
    authedFetch<RfqRead[]>(
      `${BASE}/rfqs${buildQuery(params as Record<string, string | number | boolean | undefined | null>)}`,
    ),

  create: (payload: {
    pr_id?: string | null;
    deadline?: string | null;
    notes?: string | null;
    lines: Array<{ product_sku: string; qty: string; uom?: string }>;
  }): Promise<RfqRead> =>
    authedFetch<RfqRead>(`${BASE}/rfqs`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  addResponse: (rfqId: string, payload: {
    vendor_id: string;
    unit_price?: string | null;
    currency?: string;
    lead_time_days?: number | null;
    valid_until?: string | null;
    notes?: string | null;
  }): Promise<RfqResponseRead> =>
    authedFetch<RfqResponseRead>(`${BASE}/rfqs/${rfqId}/responses`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  comparison: (rfqId: string): Promise<RfqComparisonOut> =>
    authedFetch<RfqComparisonOut>(`${BASE}/rfqs/${rfqId}/comparison`),
};

// ---------------------------------------------------------------------------
// US-ERP-03-06 — KPIs Dashboard
// ---------------------------------------------------------------------------

export type SpendPeriod = "30d" | "90d" | "365d";

export interface ProcurementKpiRead {
  open_pr_count: number;
  open_po_count: number;
  pending_invoice_count: number;
  blocked_invoice_amount: string;
  maverick_spend_pct: string;
  avg_po_lead_time_days: string | null;
  on_time_delivery_pct: string | null;
}

export interface SpendAnalysisRead {
  period_days: number;
  by_vendor: Array<{ vendor_id: string; total_amount: string }>;
  by_product: Array<{ product_sku: string; total_amount: string }>;
}

export const procurementKpiApi = {
  kpis: (): Promise<ProcurementKpiRead> =>
    authedFetch<ProcurementKpiRead>(`${BASE}/kpis`),

  spendAnalysis: (period: SpendPeriod = "30d"): Promise<SpendAnalysisRead> =>
    authedFetch<SpendAnalysisRead>(
      `${BASE}/spend-analysis${buildQuery({ period })}`,
    ),
};
