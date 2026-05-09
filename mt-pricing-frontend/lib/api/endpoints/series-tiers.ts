"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/series-tiers` y `/api/v1/admin/series-tiers`
 * (Stage 3 / Wave 11).
 */

export interface SeriesTier {
  id: string;
  code: string;
  name: string;
  rank: number;
  display_color: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SeriesTierCreatePayload {
  code: string;
  name: string;
  rank?: number;
  display_color?: string | null;
  active?: boolean;
}

export interface SeriesTierPatchPayload {
  name?: string | null;
  rank?: number | null;
  display_color?: string | null;
  active?: boolean | null;
}

export class SeriesTiersApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "SeriesTiersApiError";
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
    throw new SeriesTiersApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const seriesTiersApi = {
  listPublic: (): Promise<SeriesTier[]> =>
    authedFetch<SeriesTier[]>(`/api/v1/series-tiers`),
  list: (): Promise<SeriesTier[]> =>
    authedFetch<SeriesTier[]>(`/api/v1/admin/series-tiers`),
  create: (payload: SeriesTierCreatePayload): Promise<SeriesTier> =>
    authedFetch<SeriesTier>(`/api/v1/admin/series-tiers`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patch: (id: string, payload: SeriesTierPatchPayload): Promise<SeriesTier> =>
    authedFetch<SeriesTier>(`/api/v1/admin/series-tiers/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  remove: (id: string): Promise<void> =>
    authedFetch<void>(`/api/v1/admin/series-tiers/${id}`, { method: "DELETE" }),
};
