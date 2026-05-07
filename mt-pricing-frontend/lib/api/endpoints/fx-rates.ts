"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/fx-rates` (US-1A-05-03).
 *
 * Endpoint nuevo S3 (DIFERENTE del legacy `/api/v1/pricing/fx-rates`).
 * El legacy se mantiene para `/admin/divisas` antiguo, los nuevos clientes
 * (admin/fx-rates) usan este path raíz.
 *
 * Endpoints:
 *  - GET  /api/v1/fx-rates?from_currency=&to_currency=&only_active=&limit=
 *  - POST /api/v1/fx-rates    (RBAC fx:manage)
 */

export interface FXRateRow {
  id: string;
  from_currency: string;
  to_currency: string;
  rate: string;
  effective_from: string;
  effective_to: string | null;
  source: string | null;
  created_by: string | null;
  created_at: string;
}

export const FX_RATE_SOURCES = ["manual", "cbuae", "ecb", "imported"] as const;
export type FXRateSource = (typeof FX_RATE_SOURCES)[number];

export interface FXRateCreatePayload {
  from_currency: string;
  to_currency: string;
  rate: number | string;
  effective_from: string; // ISO 8601
  source?: FXRateSource | undefined;
  allow_retroactive?: boolean | undefined;
  reason?: string | null | undefined;
}

export interface FXRateFilters {
  from_currency?: string | undefined;
  to_currency?: string | undefined;
  only_active?: boolean | undefined;
  limit?: number | undefined;
}

export class FxRatesApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  public readonly code: string | null;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "FxRatesApiError";
    this.status = status;
    this.detail = detail;
    // Extraer error.code del ProblemDetails si está presente.
    let code: string | null = null;
    if (detail && typeof detail === "object" && "detail" in detail) {
      const inner = (detail as { detail?: unknown }).detail;
      if (inner && typeof inner === "object" && "code" in inner) {
        const c = (inner as { code?: unknown }).code;
        if (typeof c === "string") code = c;
      }
    }
    this.code = code;
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
    throw new FxRatesApiError(res.status, detail, res.statusText);
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

export const fxRatesApi = {
  list: (filters: FXRateFilters = {}): Promise<FXRateRow[]> =>
    authedFetch<FXRateRow[]>(
      `/api/v1/fx-rates${buildQuery({
        from_currency: filters.from_currency,
        to_currency: filters.to_currency,
        only_active: filters.only_active,
        limit: filters.limit,
      })}`,
    ),
  create: (payload: FXRateCreatePayload): Promise<FXRateRow> =>
    authedFetch<FXRateRow>(`/api/v1/fx-rates`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
