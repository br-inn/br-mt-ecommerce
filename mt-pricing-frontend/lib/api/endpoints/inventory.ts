"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface InventoryPositionRead {
  id: string;
  sku: string;
  supplier_code: string;
  scheme_code: string;
  qty_on_hand: string;
  map_aed: string | null;
  total_stock_value_aed: string | null;
  last_gr_id: string | null;
  last_updated_at: string | null;
  product_name: string | null;
}

export interface MAPHistoryPoint {
  gr_id: string;
  map_before: string | null;
  map_after: string;
  qty_received: string;
  received_at: string;
  po_number: string;
}

export interface InventorySummary {
  total_skus_with_stock: number;
  total_stock_value_aed: string;
  skus_without_cost: number;
  pending_gr_count: number;
}

export interface InventoryPositionFilters {
  sku?: string;
  supplier_code?: string;
  scheme_code?: string;
  has_stock?: boolean;
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class InventoryApiError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly detail: unknown,
    message?: string,
  ) {
    super(message ?? `Inventory API error ${statusCode}`);
    this.name = "InventoryApiError";
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
    throw new InventoryApiError(res.status, detail, res.statusText);
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

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

const BASE = "/api/v1/inventory";

export const inventoryApi = {
  /** Lista posiciones con filtros opcionales. */
  listPositions: (
    filters: InventoryPositionFilters = {},
  ): Promise<InventoryPositionRead[]> =>
    authedFetch<InventoryPositionRead[]>(
      `${BASE}/positions${buildQuery({
        sku: filters.sku,
        supplier_code: filters.supplier_code,
        scheme_code: filters.scheme_code,
        has_stock: filters.has_stock,
      })}`,
    ),

  /** Posiciones para un SKU específico (todas las combinaciones). */
  getPositionsBySku: (sku: string): Promise<InventoryPositionRead[]> =>
    authedFetch<InventoryPositionRead[]>(`${BASE}/positions/${encodeURIComponent(sku)}`),

  /** Historial de cambios MAP para un SKU. */
  getMAPHistory: (sku: string, limit = 50): Promise<MAPHistoryPoint[]> =>
    authedFetch<MAPHistoryPoint[]>(
      `${BASE}/positions/${encodeURIComponent(sku)}/map-history${buildQuery({ limit })}`,
    ),

  /** KPIs agregados de inventario. */
  getSummary: (): Promise<InventorySummary> =>
    authedFetch<InventorySummary>(`${BASE}/summary`),
};
