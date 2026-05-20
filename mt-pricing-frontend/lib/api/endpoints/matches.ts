"use client";

import { authedFetch } from "@/lib/api/client";

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
  image_url: string | null;
  source_url: string | null;
  delivery_category: "local_stock" | "regional" | "import" | "unknown" | null;
  price_confidence_score: number | null;
  pack_units: number | null;
  validated_by: string | null;
  validated_at: string | null;
  discarded_reason: string | null;
  calibrated_confidence: string | null;
  conf_lower: string | null;
  conf_upper: string | null;
  review_priority: "low" | "high" | null;
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

export type RefreshTaskStatus = "queued" | "running" | "done" | "failed";

export interface MatchRefreshJobResponse {
  sku: string;
  task_id: string;
  task_status: RefreshTaskStatus;
  refreshed_count: number;
  candidates: MatchCandidate[];
}

export interface MatchRefreshStatusResponse {
  sku: string;
  task_id: string;
  task_status: RefreshTaskStatus;
  refreshed_count: number;
  candidates: MatchCandidate[];
  error?: string | null;
}

export interface MatchFilters {
  sku?: string;
  status?: MatchStatus;
  channel?: MatchChannel;
  cursor?: string | null;
  limit?: number;
  include_total?: boolean;
}

export interface MatchBulkValidateResponse {
  validated: number;
  skipped: string[];
}

// --- Agente de validación ---
export type AgentMode = "shadow" | "active";
export type AgentVerdict = "auto_validate" | "auto_discard" | "human";

export interface MatchAgentConfig {
  mode: AgentMode;
  alpha: string;
  min_labels_gate: number;
  updated_at: string;
}

export interface MatchAgentConfigUpdate {
  mode?: AgentMode;
  alpha?: number;
  min_labels_gate?: number;
}

export interface MatchAgentMetrics {
  golden_labels_total: number;
  min_labels_gate: number;
  gate_reached: boolean;
  shadow_decisions: number;
  shadow_precision: number | null;
  calibrator_version: string | null;
  calibrator_brier: number | null;
  calibrator_ece: number | null;
  calibrator_trained_on: number | null;
  mode: AgentMode;
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
  refresh: (sku: string): Promise<MatchRefreshJobResponse> =>
    authedFetch<MatchRefreshJobResponse>(`/api/v1/matches/${sku}/refresh`, { method: "POST" }),
  refreshStatus: (sku: string, taskId: string): Promise<MatchRefreshStatusResponse> =>
    authedFetch<MatchRefreshStatusResponse>(`/api/v1/matches/${sku}/refresh/status/${taskId}`),
  validate: (id: string): Promise<MatchCandidate> =>
    authedFetch<MatchCandidate>(`/api/v1/matches/${id}/validate`, { method: "POST" }),
  discard: (id: string, reason?: string): Promise<MatchCandidate> =>
    authedFetch<MatchCandidate>(`/api/v1/matches/${id}/discard`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),
  clearAll: (): Promise<{ deleted: number }> =>
    authedFetch<{ deleted: number }>("/api/v1/matches", { method: "DELETE" }),
  bulkValidate: (ids: string[]): Promise<MatchBulkValidateResponse> =>
    authedFetch<MatchBulkValidateResponse>("/api/v1/matches/bulk-validate", {
      method: "POST",
      body: JSON.stringify({ ids }),
    }),
  agentConfig: (): Promise<MatchAgentConfig> =>
    authedFetch<MatchAgentConfig>("/api/v1/matches/agent/config"),
  updateAgentConfig: (body: MatchAgentConfigUpdate): Promise<MatchAgentConfig> =>
    authedFetch<MatchAgentConfig>("/api/v1/matches/agent/config", {
      method: "PUT",
      body: JSON.stringify(body),
    }),
  agentMetrics: (): Promise<MatchAgentMetrics> =>
    authedFetch<MatchAgentMetrics>("/api/v1/matches/agent/metrics"),
  revert: (id: string): Promise<MatchCandidate> =>
    authedFetch<MatchCandidate>(`/api/v1/matches/${id}/revert`, { method: "POST" }),
};
