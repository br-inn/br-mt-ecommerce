"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/currencies` (US-1A-05-01-S3).
 *
 * Endpoints:
 *  - GET   /api/v1/currencies                       (read — fx:read)
 *  - PATCH /api/v1/currencies/{code}/active         (write — currencies:manage)
 *
 * El listado completo (incluye inactivas) lo necesita la admin UI para
 * permitir reactivar.
 */

export interface CurrencyAdmin {
  code: string;
  name: string;
  symbol: string | null;
  decimals: number;
  is_base: boolean;
  active: boolean;
  created_at: string;
}

export interface CurrencyActivePatchPayload {
  active: boolean;
  reason?: string | null;
}

export class CurrenciesApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "CurrenciesApiError";
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
    throw new CurrenciesApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const currenciesApi = {
  list: (): Promise<CurrencyAdmin[]> =>
    authedFetch<CurrencyAdmin[]>(`/api/v1/currencies`),
  setActive: (
    code: string,
    payload: CurrencyActivePatchPayload,
  ): Promise<CurrencyAdmin> =>
    authedFetch<CurrencyAdmin>(
      `/api/v1/currencies/${encodeURIComponent(code)}/active`,
      {
        method: "PATCH",
        body: JSON.stringify(payload),
      },
    ),
};
