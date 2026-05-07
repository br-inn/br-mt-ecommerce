"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/pricing/fx-rates` y `/api/v1/pricing/currencies`.
 *
 * Endpoints:
 *  - GET  /api/v1/pricing/currencies                       (read-only S2)
 *  - GET  /api/v1/pricing/fx-rates?from_currency=&to_currency=
 *  - POST /api/v1/pricing/fx-rates
 */

export interface Currency {
  code: string;
  name: string;
  symbol: string | null;
  decimals: number;
  is_base: boolean;
  active: boolean;
}

export interface FXRate {
  id: string;
  from_currency: string;
  to_currency: string;
  rate: string;
  effective_from: string;
  effective_to: string | null;
  source: string | null;
  created_at: string;
}

export interface FXRateCreatePayload {
  from_currency: string;
  to_currency: string;
  rate: number | string;
  effective_from?: string | null;
  source?: string | null;
}

export interface FXRateFilters {
  from_currency?: string | undefined;
  to_currency?: string | undefined;
}

export const FX_SOURCES = ["manual", "ecb", "fixer", "cbuae"] as const;
export type FXSource = (typeof FX_SOURCES)[number];

export class FxApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "FxApiError";
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
    throw new FxApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(
  params: Record<string, string | undefined | null>,
): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    search.set(k, v);
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const fxApi = {
  listCurrencies: (): Promise<Currency[]> =>
    authedFetch<Currency[]>(`/api/v1/pricing/currencies`),
  listRates: (filters: FXRateFilters = {}): Promise<FXRate[]> =>
    authedFetch<FXRate[]>(
      `/api/v1/pricing/fx-rates${buildQuery({
        from_currency: filters.from_currency,
        to_currency: filters.to_currency,
      })}`,
    ),
  createRate: (payload: FXRateCreatePayload): Promise<FXRate> =>
    authedFetch<FXRate>(`/api/v1/pricing/fx-rates`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
