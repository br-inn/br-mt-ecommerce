"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/pricing` (Wave 2 motor v5.1).
 *
 * Endpoints (ver `app/api/routes/pricing.py`):
 *  - GET    /api/v1/pricing/prices?sku=&channel=&scheme=&status=&cursor=&limit=
 *  - POST   /api/v1/pricing/prices
 *  - GET    /api/v1/pricing/prices/{id}
 *  - POST   /api/v1/pricing/prices/{id}/approve
 *  - POST   /api/v1/pricing/prices/{id}/reject
 *  - POST   /api/v1/pricing/prices/{id}/revise
 *  - POST   /api/v1/pricing/prices/{id}/export
 *  - POST   /api/v1/pricing/prices/bulk-approve
 *  - POST   /api/v1/pricing/prices/recalculate
 *  - POST   /api/v1/pricing/calculate
 *  - POST   /api/v1/pricing/simulate
 *  - GET    /api/v1/pricing/channels
 *  - PATCH  /api/v1/pricing/channels/{code}/state
 *  - GET    /api/v1/pricing/fx-rates
 *  - POST   /api/v1/pricing/fx-rates
 */

// ---- Types ---------------------------------------------------------------

export type PriceStatus =
  | "draft"
  | "pending_review"
  | "auto_approved"
  | "approved"
  | "rejected"
  | "revised"
  | "exported"
  | "superseded"
  | "migrated";

export interface PriceAlert {
  severity: "info" | "warning" | "critical";
  code: string;
  message: string;
  [extra: string]: unknown;
}

export interface PriceRow {
  id: string;
  product_sku: string;
  channel_id: string;
  scheme_code: string;
  amount: string; // Decimal serialized
  pvp_min: string | null;
  margin_pct: string;
  currency: string;
  rule_applied: string | null;
  formula: string | null;
  breakdown: Record<string, unknown>;
  alerts: PriceAlert[];
  status: PriceStatus;
  proposed_by: string | null;
  approved_by: string | null;
  approved_at: string | null;
  rejection_reason: string | null;
  valid_from: string;
  valid_to: string | null;
  created_at: string;
  updated_at: string;
}

export interface PriceApprovalEvent {
  id: string;
  price_id: string;
  actor_id: string;
  from_status: PriceStatus;
  to_status: PriceStatus;
  reason: string | null;
  metadata_jsonb: Record<string, unknown>;
  created_at: string;
}

export interface PriceDetail extends PriceRow {
  approval_events: PriceApprovalEvent[];
}

export interface PriceListResponse {
  items: PriceRow[];
  cursor: { next: string | null; prev: string | null };
  total: number | null;
  page_size: number;
}

export interface PricingResult {
  amount: string;
  pvp_min: string | null;
  margin_pct: string;
  rule_applied: string;
  formula: string;
  breakdown: Record<string, unknown>;
  alerts: PriceAlert[];
  fx_at: string | null;
  has_velocity_premium: boolean;
  has_critical_alerts: boolean;
  has_warnings: boolean;
  cap_applied: boolean;
  floor_applied: boolean;
}

export interface Channel {
  id: string;
  code: string;
  name: string;
  state:
    | "inactive"
    | "pre_launch"
    | "pilot"
    | "live"
    | "paused"
    | "deprecated";
  schemes_supported: string[];
  state_history: Array<Record<string, unknown>>;
  created_at: string;
  updated_at: string;
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

export interface PriceFilters {
  sku?: string | undefined;
  channel?: string | undefined;
  scheme?: string | undefined;
  status?: PriceStatus | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
  include_total?: boolean | undefined;
}

export interface PriceProposePayload {
  product_sku: string;
  channel_code: string;
  scheme_code: string;
  market?: Record<string, unknown> | null;
  master_data?: Record<string, unknown> | null;
}

export interface PriceSimulatePayload {
  product_sku: string;
  channel_code: string;
  scheme_code: string;
  scenario_overrides?: Record<string, unknown> | null;
}

// ---- Internals -----------------------------------------------------------

export class PricingApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "PricingApiError";
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
    throw new PricingApiError(res.status, detail, res.statusText);
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

export const pricingApi = {
  // Prices
  list: (filters: PriceFilters = {}): Promise<PriceListResponse> =>
    authedFetch<PriceListResponse>(
      `/api/v1/pricing/prices${buildQuery({
        sku: filters.sku,
        channel: filters.channel,
        scheme: filters.scheme,
        status: filters.status,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
        include_total: filters.include_total,
      })}`,
    ),
  get: (id: string): Promise<PriceDetail> =>
    authedFetch<PriceDetail>(`/api/v1/pricing/prices/${id}`),
  propose: (payload: PriceProposePayload): Promise<PriceRow> =>
    authedFetch<PriceRow>(`/api/v1/pricing/prices`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  approve: (id: string, reason?: string): Promise<PriceRow> =>
    authedFetch<PriceRow>(`/api/v1/pricing/prices/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  reject: (id: string, reason: string): Promise<PriceRow> =>
    authedFetch<PriceRow>(`/api/v1/pricing/prices/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),
  revise: (id: string, newAmount: string, reason: string): Promise<PriceRow> =>
    authedFetch<PriceRow>(`/api/v1/pricing/prices/${id}/revise`, {
      method: "POST",
      body: JSON.stringify({ new_amount: newAmount, reason }),
    }),
  export: (id: string): Promise<PriceRow> =>
    authedFetch<PriceRow>(`/api/v1/pricing/prices/${id}/export`, {
      method: "POST",
    }),
  // Nota: backend usa `comment` (no `reason`) — campo obligatorio ≥10 chars.
  bulkApprove: (ids: string[], comment?: string): Promise<unknown> =>
    authedFetch(`/api/v1/pricing/prices/bulk-approve`, {
      method: "POST",
      body: JSON.stringify({ price_ids: ids, comment: comment ?? "" }),
    }),
  recalcAll: (): Promise<{ task_id: string; status: string }> =>
    authedFetch(`/api/v1/pricing/prices/recalculate`, { method: "POST" }),

  // Calculate / simulate
  calculate: (payload: PriceProposePayload): Promise<PricingResult> =>
    authedFetch<PricingResult>(`/api/v1/pricing/calculate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  simulate: (payload: PriceSimulatePayload): Promise<PricingResult> =>
    authedFetch<PricingResult>(`/api/v1/pricing/simulate`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // Channels
  channels: (state?: string): Promise<Channel[]> =>
    authedFetch<Channel[]>(
      `/api/v1/pricing/channels${buildQuery({ state })}`,
    ),
  setChannelState: (
    code: string,
    state: string,
    reason?: string,
  ): Promise<Channel> =>
    authedFetch<Channel>(`/api/v1/pricing/channels/${code}/state`, {
      method: "PATCH",
      body: JSON.stringify({ state, reason: reason ?? null }),
    }),

  // FX rates
  fxRates: (
    from_currency?: string,
    to_currency?: string,
  ): Promise<FXRate[]> =>
    authedFetch<FXRate[]>(
      `/api/v1/pricing/fx-rates${buildQuery({ from_currency, to_currency })}`,
    ),
  createFXRate: (payload: {
    from_currency: string;
    to_currency: string;
    rate: string;
    effective_from?: string | null;
    source?: string | null;
  }): Promise<FXRate> =>
    authedFetch<FXRate>(`/api/v1/pricing/fx-rates`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
