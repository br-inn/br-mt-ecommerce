"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/admin/calibrator` (US-1A-DEV-01 frontend / S5).
 *
 * Endpoints (Agente C S5 — calibrator training pipeline US-1A-09-07):
 *  - GET   /api/v1/admin/calibrator/active            → versión activa + métricas
 *  - POST  /api/v1/admin/calibrator/train             { dataset_path, version }
 *  - POST  /api/v1/admin/calibrator/promote/{version} → marca version como active
 */

export interface CalibratorMetrics {
  ece: number | null;
  brier: number | null;
  log_loss: number | null;
  dataset_size: number | null;
}

export interface CalibratorVersion {
  version: string;
  active: boolean;
  fitted_at: string;
  dataset_hash: string | null;
  metrics: CalibratorMetrics;
  artifact_url: string | null;
}

export interface CalibratorActiveResponse {
  active: CalibratorVersion | null;
  versions: CalibratorVersion[];
}

export interface CalibratorTrainPayload {
  dataset_path: string;
  version: string;
}

export interface CalibratorTrainResponse {
  task_id: string;
  status: "queued";
  version: string;
}

export interface CalibratorPromoteResponse {
  active_version: string;
  promoted_at: string;
}

export class AdminCalibratorApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "AdminCalibratorApiError";
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
    throw new AdminCalibratorApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const adminCalibratorApi = {
  active: (): Promise<CalibratorActiveResponse> =>
    authedFetch<CalibratorActiveResponse>(`/api/v1/admin/calibrator/active`),
  train: (payload: CalibratorTrainPayload): Promise<CalibratorTrainResponse> =>
    authedFetch<CalibratorTrainResponse>(`/api/v1/admin/calibrator/train`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  promote: (version: string): Promise<CalibratorPromoteResponse> =>
    authedFetch<CalibratorPromoteResponse>(
      `/api/v1/admin/calibrator/promote/${encodeURIComponent(version)}`,
      { method: "POST" },
    ),
};
