"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/suppliers` — alineado al backend real.
 *
 * Contrato confirmado (Wave 2A):
 *  - PK = `code` (string TEXT) — no UUID.
 *  - `contract_currency` ISO-4217 obligatorio (FK→ currencies).
 *  - Sin `country` (BR-MT no segmenta por país).
 *  - DELETE bloqueado (405) — soft delete vía PATCH active=false.
 *  - Cursor opaco base64url(json({"code": "..."})).
 *  - Paginación: { items, cursor: { next, prev }, page_size, total }.
 *
 * Endpoints:
 *  - GET   /api/v1/suppliers?q=&active=&contract_currency=&cursor=&limit=&include_total=
 *  - POST  /api/v1/suppliers
 *  - GET   /api/v1/suppliers/{code}
 *  - PUT   /api/v1/suppliers/{code}      (replace)
 *  - PATCH /api/v1/suppliers/{code}      (parcial)
 *  - DELETE /api/v1/suppliers/{code}     (405)
 */

// ---- Types ----------------------------------------------------------------

export interface Supplier {
  code: string;
  name: string;
  contact_email: string | null;
  contact_phone: string | null;
  contract_currency: string;
  lead_time_days: number | null;
  payment_terms: string | null;
  notes: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SupplierListResponse {
  items: Supplier[];
  cursor: { next: string | null; prev: string | null };
  page_size: number;
  total: number | null;
}

export interface SupplierCreatePayload {
  code: string;
  name: string;
  contact_email?: string | null | undefined;
  contact_phone?: string | null | undefined;
  contract_currency: string;
  lead_time_days?: number | null | undefined;
  payment_terms?: string | null | undefined;
  notes?: string | null | undefined;
  active?: boolean | undefined;
}

/** Patch payload — todos los campos opcionales (incluido active). */
export interface SupplierPatchPayload {
  name?: string | undefined;
  contact_email?: string | null | undefined;
  contact_phone?: string | null | undefined;
  contract_currency?: string | undefined;
  lead_time_days?: number | null | undefined;
  payment_terms?: string | null | undefined;
  notes?: string | null | undefined;
  active?: boolean | undefined;
}

export interface SupplierFilters {
  search?: string | undefined;
  active?: boolean | undefined;
  /** Filtro por moneda contractual (ISO-4217). */
  contract_currency?: string | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
}

// ---- Errors ---------------------------------------------------------------

export class SuppliersApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "SuppliersApiError";
    this.status = status;
    this.detail = detail;
  }

  /** Mapea Pydantic validation errors → field path → message. */
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
    throw new SuppliersApiError(res.status, detail, res.statusText);
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

export const suppliersApi = {
  list: (filters: SupplierFilters = {}): Promise<SupplierListResponse> =>
    authedFetch<SupplierListResponse>(
      `/api/v1/suppliers${buildQuery({
        q: filters.search,
        active: filters.active,
        contract_currency: filters.contract_currency,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
      })}`,
    ),
  get: (code: string): Promise<Supplier> =>
    authedFetch<Supplier>(`/api/v1/suppliers/${encodeURIComponent(code)}`),
  create: (payload: SupplierCreatePayload): Promise<Supplier> =>
    authedFetch<Supplier>(`/api/v1/suppliers`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patch: (code: string, payload: SupplierPatchPayload): Promise<Supplier> =>
    authedFetch<Supplier>(`/api/v1/suppliers/${encodeURIComponent(code)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  setActive: (code: string, active: boolean): Promise<Supplier> =>
    authedFetch<Supplier>(`/api/v1/suppliers/${encodeURIComponent(code)}`, {
      method: "PATCH",
      body: JSON.stringify({ active }),
    }),
};

/** Lista canónica de códigos ISO 4217 utilizados en el form. */
export const SUPPLIER_CURRENCIES = ["AED", "EUR", "USD", "SAR", "GBP"] as const;
export type SupplierCurrency = (typeof SUPPLIER_CURRENCIES)[number];
