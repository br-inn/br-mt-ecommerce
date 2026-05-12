"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export type HumanQueueLabel = "accept" | "reject" | "skip";

export interface HumanQueueItem {
  id: string;
  product_sku: string;
  channel: string;
  external_id: string;
  brand: string | null;
  title: string;
  price_aed: string | null;
  specs_jsonb: Record<string, unknown>;
  kind: string;
  score: number;
  status: string;
  calibrated_confidence: string | null;
  label: HumanQueueLabel | null;
  reviewer_user_id: string | null;
  reviewed_at: string | null;
  validated_by: string | null;
  validated_at: string | null;
  discarded_reason: string | null;
  created_at: string;
  updated_at: string;
  // VLM Judge (US-F15-02-02, AC#5/AC#6) — null para viewers y cuando VLM no corrió
  judge_rationale: string | null;
  judge_image_regions: Record<string, string>[] | null;
}

export interface HumanQueueListResponse {
  items: HumanQueueItem[];
  total: number;
  limit: number;
  offset: number;
  confidence_threshold: number;
}

export interface HumanQueueFilters {
  limit?: number;
  offset?: number;
  confidence_threshold?: number;
}

export interface LabelPayload {
  label: HumanQueueLabel;
}

export class HumanQueueApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "HumanQueueApiError";
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
    throw new HumanQueueApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(filters: HumanQueueFilters): string {
  const params = new URLSearchParams();
  if (filters.limit !== undefined) params.set("limit", String(filters.limit));
  if (filters.offset !== undefined) params.set("offset", String(filters.offset));
  if (filters.confidence_threshold !== undefined) {
    params.set("confidence_threshold", String(filters.confidence_threshold));
  }
  const qs = params.toString();
  return qs ? `?${qs}` : "";
}

export const humanQueueApi = {
  list: (filters: HumanQueueFilters = {}): Promise<HumanQueueListResponse> =>
    authedFetch<HumanQueueListResponse>(
      `/api/v1/human-queue${buildQuery(filters)}`,
    ),

  label: (matchId: string, payload: LabelPayload): Promise<HumanQueueItem> =>
    authedFetch<HumanQueueItem>(
      `/api/v1/human-queue/${encodeURIComponent(matchId)}/label`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
};
