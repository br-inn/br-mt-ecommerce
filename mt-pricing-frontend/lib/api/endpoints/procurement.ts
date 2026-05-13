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
  product_id: string | null;
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
  product_id?: string | null;
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
  product_id: string;
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
  product_id: string;
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
    product_id?: string;
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
