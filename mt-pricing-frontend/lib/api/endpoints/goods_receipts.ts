"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type { POLineRead } from "@/lib/api/endpoints/purchase_orders";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type GRStatus = "pending" | "processed" | "error";

export interface ActualBreakdown {
  fob_eur?: string | null;
  flete_eur?: string | null;
  arancel_base_eur?: string | null;
  arancel_pct?: string | null;
  [key: string]: unknown;
}

export interface GoodsReceiptRead {
  id: string;
  po_line_id: string;
  qty_received: string;
  received_at: string;
  received_by: string | null;
  actual_unit_price: string | null;
  actual_breakdown: ActualBreakdown;
  map_before: string | null;
  map_after: string | null;
  fx_rate_id: string | null;
  notes: string | null;
  status: GRStatus;
  processed_at: string | null;
  created_at: string;
  po_line: POLineRead;
}

export interface GoodsReceiptStatusRead {
  gr_id: string;
  status: GRStatus;
  map_before: string | null;
  map_after: string | null;
  processed_at: string | null;
  error_summary: string | null;
}

export interface GRCreatePayload {
  po_line_id: string;
  qty_received: string;
  received_at?: string | null;
  actual_unit_price?: string | null;
  actual_breakdown?: ActualBreakdown;
  notes?: string | null;
  force?: boolean;
}

export interface GRFilters {
  sku?: string;
  po_id?: string;
  status?: GRStatus | "";
  cursor?: string;
  limit?: number;
}

export interface GRCursor {
  next: string | null;
  prev?: string | null;
}

export interface GRListResponse {
  items: GoodsReceiptRead[];
  cursor: GRCursor;
  page_size: number;
  total?: number | null;
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class GoodsReceiptsApiError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly detail: unknown,
    message?: string,
  ) {
    super(message ?? `GoodsReceipts API error ${statusCode}`);
    this.name = "GoodsReceiptsApiError";
  }
}

// ---------------------------------------------------------------------------
// Authenticated fetch helper
// ---------------------------------------------------------------------------

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
    throw new GoodsReceiptsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as unknown as T;
  return res.json() as Promise<T>;
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

const BASE = "/api/v1/goods-receipts";

// ---------------------------------------------------------------------------
// API client
// ---------------------------------------------------------------------------

export const goodsReceiptsApi = {
  create: (payload: GRCreatePayload): Promise<GoodsReceiptRead> =>
    authedFetch<GoodsReceiptRead>(BASE, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  list: (filters: GRFilters = {}): Promise<GRListResponse> =>
    authedFetch<GRListResponse>(
      `${BASE}${buildQuery({
        sku: filters.sku,
        po_id: filters.po_id,
        status: filters.status,
        cursor: filters.cursor,
        limit: filters.limit,
      })}`,
    ),

  get: (id: string): Promise<GoodsReceiptRead> =>
    authedFetch<GoodsReceiptRead>(`${BASE}/${id}`),

  getStatus: (id: string): Promise<GoodsReceiptStatusRead> =>
    authedFetch<GoodsReceiptStatusRead>(`${BASE}/${id}/status`),

  retry: (id: string): Promise<GoodsReceiptRead> =>
    authedFetch<GoodsReceiptRead>(`${BASE}/${id}/retry`, { method: "POST" }),
};
