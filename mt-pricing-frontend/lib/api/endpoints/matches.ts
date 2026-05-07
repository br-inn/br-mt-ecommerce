"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export type MatchChannel = "amazon_uae" | "noon_uae";
export type MatchKind = "peer" | "drop" | "unknown";
export type MatchStatus = "pending" | "validated" | "discarded";

export interface MatchCandidate {
  id: string;
  product_sku: string;
  channel: MatchChannel;
  external_id: string;
  brand: string | null;
  title: string;
  price_aed: string | null;
  delivery_text: string | null;
  specs_jsonb: Record<string, unknown>;
  kind: MatchKind;
  score: number;
  status: MatchStatus;
  validated_by: string | null;
  validated_at: string | null;
  discarded_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface MatchCandidateDetail extends MatchCandidate {
  scoring: Record<string, unknown> | null;
}

export interface MatchListResponse {
  items: MatchCandidate[];
  cursor: { next: string | null; prev: string | null };
  page_size: number;
  total: number | null;
}

export interface MatchRefreshResponse {
  sku: string;
  refreshed_count: number;
  candidates: MatchCandidate[];
}

export interface MatchFilters {
  sku?: string;
  status?: MatchStatus;
  channel?: MatchChannel;
  cursor?: string | null;
  limit?: number;
  include_total?: boolean;
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
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    search.set(k, String(v));
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const matchesApi = {
  list: (f: MatchFilters = {}): Promise<MatchListResponse> =>
    authedFetch<MatchListResponse>(
      `/api/v1/matches${buildQuery({
        sku: f.sku,
        status: f.status,
        channel: f.channel,
        cursor: f.cursor ?? undefined,
        limit: f.limit,
        include_total: f.include_total,
      })}`,
    ),
  get: (id: string): Promise<MatchCandidateDetail> =>
    authedFetch<MatchCandidateDetail>(`/api/v1/matches/${id}`),
  refresh: (sku: string): Promise<MatchRefreshResponse> =>
    authedFetch<MatchRefreshResponse>(`/api/v1/matches/${sku}/refresh`, { method: "POST" }),
  validate: (id: string): Promise<MatchCandidate> =>
    authedFetch<MatchCandidate>(`/api/v1/matches/${id}/validate`, { method: "POST" }),
  discard: (id: string, reason?: string): Promise<MatchCandidate> =>
    authedFetch<MatchCandidate>(`/api/v1/matches/${id}/discard`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
};
