"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// ---- Types ------------------------------------------------------------------

export type UnmatchedOfferMarketplace = "amazon_uae" | "noon_uae";
export type UnmatchedOfferStatus = "pending" | "matched" | "exhausted";

export interface UnmatchedOfferResponse {
  id: string;
  marketplace: UnmatchedOfferMarketplace;
  external_id: string;
  title: string;
  brand: string | null;
  price_aed: string | null; // Decimal as string
  delivery_text: string | null;
  specs_jsonb: Record<string, unknown>;
  image_url: string | null;
  source_url: string | null;
  source_sku: string | null;
  match_attempts: number;
  matched_at: string | null; // ISO datetime
  scraped_at: string; // ISO datetime
  created_at: string;
  status: UnmatchedOfferStatus;
  has_embedding: boolean;
}

export interface UnmatchedOffersStats {
  total_pending: number;
  total_matched: number;
  total_exhausted: number;
  matched_last_24h: number;
  scraped_last_7d: number;
}

export interface UnmatchedOffersListResponse {
  items: UnmatchedOfferResponse[];
  next_cursor: string | null;
  total: number | null;
}

export interface UnmatchedOffersFilters {
  marketplace?: UnmatchedOfferMarketplace | null;
  status?: UnmatchedOfferStatus | null;
  source_sku?: string | null;
  q?: string | null;
  cursor?: string | null;
  limit?: number;
}

// ---- HTTP helpers -----------------------------------------------------------

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
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new Error(msg);
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

// ---- API object -------------------------------------------------------------

export const unmatchedOffersApi = {
  list: (f: UnmatchedOffersFilters = {}): Promise<UnmatchedOffersListResponse> =>
    authedFetch<UnmatchedOffersListResponse>(
      `/api/v1/unmatched-offers${buildQuery({
        marketplace: f.marketplace ?? undefined,
        status: f.status ?? undefined,
        source_sku: f.source_sku ?? undefined,
        q: f.q ?? undefined,
        cursor: f.cursor ?? undefined,
        limit: f.limit,
      })}`,
    ),

  stats: (): Promise<UnmatchedOffersStats> =>
    authedFetch<UnmatchedOffersStats>("/api/v1/unmatched-offers/stats"),
};
