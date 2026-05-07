"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export type DiffStatus = "match" | "drift" | "missing" | "queued";
export type BuyBoxState = "own" | "competitor" | "none";

export interface FieldDiff {
  field: string;
  mt: string | null;
  live: string | null;
  status: DiffStatus;
  lang?: string | null;
  is_mono?: boolean;
}

export interface DiffSummary {
  match: number;
  drift: number;
  missing: number;
  queued: number;
}

export interface ChannelListing {
  id: string;
  product_sku: string;
  channel_code: string;
  external_id: string;
  buybox_state: BuyBoxState;
  buybox_pct_7d: string | null;
  stock_qty: number | null;
  rating: string | null;
  reviews_count: number | null;
  last_sync_at: string | null;
  diff_summary: DiffSummary;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DiffResponse {
  channel_code: string;
  sku: string;
  external_id: string;
  diffs: FieldDiff[];
  summary: DiffSummary;
  fetched_at: string | null;
}

export interface SyncLogEntry {
  id: string;
  channel_code: string;
  product_sku: string | null;
  event_type: "pull" | "push" | "diff";
  ok: boolean;
  summary: string | null;
  duration_ms: number | null;
  created_at: string;
}

export interface PublishResponse {
  channel_code: string;
  sku: string;
  external_id: string;
  ok: boolean;
  accepted_fields: string[];
  rejected_fields: string[];
  message: string | null;
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

export const channelMirrorApi = {
  listings: (channel: string, params: { cursor?: string | null; limit?: number } = {}) => {
    const q = new URLSearchParams();
    if (params.cursor) q.set("cursor", params.cursor);
    if (params.limit !== undefined) q.set("limit", String(params.limit));
    const qs = q.toString();
    return authedFetch<{ items: ChannelListing[]; cursor: { next: string | null; prev: string | null }; page_size: number; total: number | null }>(
      `/api/v1/channels/${channel}/listings${qs ? `?${qs}` : ""}`,
    );
  },
  diff: (channel: string, sku: string): Promise<DiffResponse> =>
    authedFetch<DiffResponse>(`/api/v1/channels/${channel}/${sku}/diff`),
  sync: (channel: string, sku: string): Promise<DiffResponse> =>
    authedFetch<DiffResponse>(`/api/v1/channels/${channel}/${sku}/sync`, { method: "POST" }),
  publish: (channel: string, sku: string, fields?: string[]): Promise<PublishResponse> =>
    authedFetch<PublishResponse>(`/api/v1/channels/${channel}/${sku}/publish`, {
      method: "POST",
      body: JSON.stringify(fields ? { fields } : {}),
    }),
  syncLog: (channel: string, limit = 5): Promise<SyncLogEntry[]> =>
    authedFetch<SyncLogEntry[]>(`/api/v1/channels/${channel}/sync-log?limit=${limit}`),
};
