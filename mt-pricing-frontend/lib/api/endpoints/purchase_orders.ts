"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export type POStatus =
  | "draft"
  | "confirmed"
  | "partial"
  | "received"
  | "cancelled";

export interface LandedCostBreakdown {
  fob_eur?: string | null;
  flete_eur?: string | null;
  arancel_base_eur?: string | null;
  arancel_pct?: string | null;
  [key: string]: unknown;
}

export interface POLineRead {
  id: string;
  po_id: string;
  sku: string;
  scheme_code: string;
  qty_ordered: string;
  qty_received: string;
  unit_price: string;
  landed_cost_breakdown: LandedCostBreakdown;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderRead {
  id: string;
  po_number: string;
  supplier_code: string | null;
  currency: string | null;
  notes: string | null;
  status: POStatus;
  confirmed_at: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
}

export interface PurchaseOrderDetail extends PurchaseOrderRead {
  lines: POLineRead[];
  gr_count: number;
}

export interface POListResponse {
  items: PurchaseOrderRead[];
  cursor: { next: string | null; prev: string | null };
  total: number | null;
  page_size: number;
}

export interface POLineCreatePayload {
  sku: string;
  scheme_code: string;
  qty_ordered: string;
  unit_price: string;
  landed_cost_breakdown?: LandedCostBreakdown;
}

export interface POCreatePayload {
  po_number: string;
  supplier_code?: string | null;
  currency?: string | null;
  notes?: string | null;
  lines?: POLineCreatePayload[];
}

export interface POUpdatePayload {
  po_number?: string | null;
  supplier_code?: string | null;
  currency?: string | null;
  notes?: string | null;
}

export interface POLineUpdatePayload {
  qty_ordered?: string | null;
  unit_price?: string | null;
  landed_cost_breakdown?: LandedCostBreakdown | null;
}

export interface POFilters {
  supplier_code?: string | undefined;
  status?: POStatus | "" | undefined;
  q?: string | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
}

export class PurchaseOrdersApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "PurchaseOrdersApiError";
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
    throw new PurchaseOrdersApiError(res.status, detail, res.statusText);
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

const BASE = "/api/v1/purchase-orders";

export const purchaseOrdersApi = {
  list: (filters: POFilters = {}): Promise<POListResponse> =>
    authedFetch<POListResponse>(
      `${BASE}${buildQuery({
        supplier_code: filters.supplier_code,
        status: filters.status,
        q: filters.q,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
      })}`,
    ),

  get: (id: string): Promise<PurchaseOrderDetail> =>
    authedFetch<PurchaseOrderDetail>(`${BASE}/${id}`),

  create: (payload: POCreatePayload): Promise<PurchaseOrderRead> =>
    authedFetch<PurchaseOrderRead>(BASE, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  update: (id: string, payload: POUpdatePayload): Promise<PurchaseOrderRead> =>
    authedFetch<PurchaseOrderRead>(`${BASE}/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  confirm: (id: string): Promise<PurchaseOrderRead> =>
    authedFetch<PurchaseOrderRead>(`${BASE}/${id}/confirm`, { method: "POST" }),

  cancel: (id: string): Promise<PurchaseOrderRead> =>
    authedFetch<PurchaseOrderRead>(`${BASE}/${id}/cancel`, { method: "POST" }),

  delete: (id: string): Promise<void> =>
    authedFetch<void>(`${BASE}/${id}`, { method: "DELETE" }),

  addLine: (poId: string, payload: POLineCreatePayload): Promise<POLineRead> =>
    authedFetch<POLineRead>(`${BASE}/${poId}/lines`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  updateLine: (
    poId: string,
    lineId: string,
    payload: POLineUpdatePayload,
  ): Promise<POLineRead> =>
    authedFetch<POLineRead>(`${BASE}/${poId}/lines/${lineId}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),

  deleteLine: (poId: string, lineId: string): Promise<void> =>
    authedFetch<void>(`${BASE}/${poId}/lines/${lineId}`, { method: "DELETE" }),
};
