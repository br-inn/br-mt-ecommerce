"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/costs` (Wave 2A).
 *
 * Endpoints:
 *  - GET    /api/v1/costs?product_sku=&scheme=&supplier=&cursor=&limit=&include_total=
 *  - POST   /api/v1/costs
 *  - GET    /api/v1/costs/{id}
 *  - PATCH  /api/v1/costs/{id}
 *  - DELETE /api/v1/costs/{id}
 *
 * El backend devuelve { items, cursor: { next }, page_size, total }.
 */

export interface CostBreakdown {
  fob?: number | string | null;
  freight?: number | string | null;
  customs?: number | string | null;
  fba_fee?: number | string | null;
  fbm_fee?: number | string | null;
  payment_fee?: number | string | null;
  marketing?: number | string | null;
  storage?: number | string | null;
  ppc?: number | string | null;
  otros?: number | string | null;
  [k: string]: number | string | null | undefined;
}

export interface Cost {
  id: string;
  // ── Canonical (US-1A-04-02) ───────────────────────────────────────
  sku: string;
  scheme_code: string;
  supplier_code: string | null;
  currency_origin: string;
  fx_rate_id: string | null;
  breakdown: CostBreakdown;
  scheme_landed_aed: string | null;
  effective_at: string;
  status: "active" | "superseded";
  fx_inferred: boolean;
  version: number;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
  // ── Legacy aliases ────────────────────────────────────────────────
  product_sku: string;
  total: string | null;
  currency: string;
  fx_at: string | null;
  valid_from: string;
  valid_to: string | null;
}

export interface CostWarning {
  code: string; // e.g. "unknown_breakdown_field"
  field: string;
}

/** Response del POST/PUT NUEVO motor (US-1A-04-03). */
export interface CostCreatedResponse {
  cost: Cost;
  warnings: CostWarning[];
}

export interface CostMissingItem {
  sku: string;
  name: string | null;
}

export interface CostsListResponse {
  items: Cost[];
  cursor: { next: string | null; prev: string | null };
  page_size: number;
  total: number | null;
}

/**
 * NUEVO payload para POST /costs (US-1A-04-03). Reemplaza al legacy:
 * - `sku` (canonical) en lugar de `product_sku`.
 * - `currency_origin` en lugar de `currency`.
 * - `effective_at` mandatory (ISO TZ).
 * - Sin `total` — el backend lo calcula vía trigger.
 *
 * Para no romper clientes que aún envían `product_sku`/`currency`/`total`,
 * se conserva `LegacyCostCreatePayload`. El cliente nuevo debe usar `CostCreatePayload`.
 */
export interface CostCreatePayload {
  sku: string;
  scheme_code: string;
  supplier_code?: string | null | undefined;
  currency_origin: string;
  effective_at: string; // ISO 8601 with TZ.
  breakdown: CostBreakdown;
  fx_rate_id?: string | null | undefined;
  fx_inferred?: boolean | undefined;
}

/** Payload del PUT versionado (US-1A-04-03 AC#6). */
export interface CostUpdatePayload {
  breakdown?: CostBreakdown | undefined;
  effective_at?: string | undefined;
  currency_origin?: string | undefined;
  fx_rate_id?: string | null | undefined;
  fx_inferred?: boolean | undefined;
}

/** Legacy — usado por el endpoint PATCH deprecated. */
export interface LegacyCostCreatePayload {
  product_sku: string;
  scheme_code: string;
  supplier_code?: string | null | undefined;
  breakdown: CostBreakdown;
  total: number | string;
  currency: string;
  valid_from?: string | null | undefined;
  valid_to?: string | null | undefined;
}

export interface CostPatchPayload {
  scheme_code?: string | undefined;
  supplier_code?: string | null | undefined;
  breakdown?: CostBreakdown | undefined;
  total?: number | string | undefined;
  currency?: string | undefined;
  valid_from?: string | null | undefined;
  valid_to?: string | null | undefined;
}

export interface CostFilters {
  product_sku?: string | undefined;
  scheme?: string | undefined;
  supplier?: string | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
  include_total?: boolean | undefined;
}

// Esquemas válidos (alineado con backend enum).
export const COST_SCHEMES = [
  "FBA",
  "FBM",
  "DIRECT_B2C",
  "DIRECT_B2B",
  "MARKETPLACE",
] as const;
export type CostScheme = (typeof COST_SCHEMES)[number];

// ---- Errors ---------------------------------------------------------------

export class CostsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "CostsApiError";
    this.status = status;
    this.detail = detail;
  }

  public fieldErrors(): Record<string, string> | null {
    const detail = this.detail;
    if (!detail || typeof detail !== "object") return null;
    const arr = (detail as { detail?: unknown }).detail;
    if (!Array.isArray(arr)) return null;
    const out: Record<string, string> = {};
    for (const it of arr) {
      if (!it || typeof it !== "object") continue;
      const loc = (it as { loc?: unknown }).loc;
      const msg = (it as { msg?: unknown }).msg;
      if (Array.isArray(loc) && typeof msg === "string") {
        const key = loc.filter((p) => p !== "body").join(".");
        if (key) out[key] = msg;
      }
    }
    return Object.keys(out).length > 0 ? out : null;
  }
}

// ---- Internals ------------------------------------------------------------

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
    throw new CostsApiError(res.status, detail, res.statusText);
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

// ---- API ------------------------------------------------------------------

export const costsApi = {
  list: (filters: CostFilters = {}): Promise<CostsListResponse> =>
    authedFetch<CostsListResponse>(
      `/api/v1/costs${buildQuery({
        product_sku: filters.product_sku,
        scheme: filters.scheme,
        supplier: filters.supplier,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
        include_total: filters.include_total,
      })}`,
    ),
  get: (id: string): Promise<Cost> =>
    authedFetch<Cost>(`/api/v1/costs/${encodeURIComponent(id)}`),
  /** POST nuevo motor — devuelve { cost, warnings }. */
  create: (payload: CostCreatePayload): Promise<CostCreatedResponse> =>
    authedFetch<CostCreatedResponse>(`/api/v1/costs`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  /** PUT versionado — anterior pasa a 'superseded', nueva con version+1. */
  update: (id: string, payload: CostUpdatePayload): Promise<CostCreatedResponse> =>
    authedFetch<CostCreatedResponse>(`/api/v1/costs/${encodeURIComponent(id)}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  patch: (id: string, payload: CostPatchPayload): Promise<Cost> =>
    authedFetch<Cost>(`/api/v1/costs/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  delete: (id: string): Promise<void> =>
    authedFetch<void>(`/api/v1/costs/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  /** GET /products/{sku}/costs — costes activos del SKU. */
  listForSku: (sku: string, onlyActive = true): Promise<Cost[]> =>
    authedFetch<Cost[]>(
      `/api/v1/products/${encodeURIComponent(sku)}/costs${buildQuery({
        only_active: onlyActive,
      })}`,
    ),
  /** GET /costs/missing — SKUs sin coste activo para un scheme. */
  missingForScheme: (
    schemeCode: string,
    limit = 1000,
  ): Promise<CostMissingItem[]> =>
    authedFetch<CostMissingItem[]>(
      `/api/v1/costs/missing${buildQuery({ scheme_code: schemeCode, limit })}`,
    ),
};
