"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para los endpoints S4 del pricing engine end-to-end
 * (US-1B-01-06): bulk-publish, recalc batch, revise. Convive con el cliente
 * `pricing.ts` (Wave 2) — cuando los endpoints S4 se solidifiquen se podría
 * fusionar.
 *
 * Endpoints (Agente B Sprint 4):
 *  - POST /api/v1/pricing/prices/bulk-publish
 *      → { task_id, total, queued }
 *  - POST /api/v1/pricing/prices/recalculate
 *      → { task_id, status }
 *  - POST /api/v1/pricing/prices/{id}/revise
 *      → PriceDetail (delegado a `pricing.ts`, re-export por conveniencia).
 *  - GET  /api/v1/pricing/tasks/{task_id}/progress
 *      → ProgressEvent
 */

export interface BulkPublishPayload {
  /** IDs de propuestas a publicar (status approved/auto_approved). */
  price_ids: string[];
  /** Override channel — todos los IDs deben pertenecer al mismo canal. */
  channel_code?: string | undefined;
  /** Razón opcional para el audit log. */
  reason?: string | undefined;
}

export interface BulkPublishResult {
  task_id: string;
  total: number;
  queued: number;
  status: string;
}

export type RecalcScope = "single" | "channel" | "family" | "all";

export interface RecalcPayload {
  scope: RecalcScope;
  sku?: string | undefined;
  channel_code?: string | undefined;
  family?: string | undefined;
  /** Si true, sólo retorna preview con los counts esperados (no encola). */
  dry_run?: boolean | undefined;
  /** Identificador del trigger para auditoría (`fx_change`, `cost_change`, `manual`). */
  trigger?: "fx_change" | "cost_change" | "manual" | undefined;
  fx_rate_id?: string | undefined;
}

export interface RecalcPreview {
  total_skus: number;
  total_channels: number;
  total_schemes: number;
  total_proposals: number;
  eta_seconds: number;
}

export interface RecalcResult {
  task_id: string;
  status: "queued" | "running" | "success" | "failed";
}

export interface ProgressEvent {
  task_id: string;
  status: "queued" | "running" | "success" | "failed";
  total: number;
  processed: number;
  succeeded: number;
  failed: number;
  eta_seconds: number | null;
  failed_details?: Array<{ sku: string; error_code: string; message?: string }>;
  started_at: string | null;
  finished_at: string | null;
}

// ---------- internals -------------------------------------------------------

export class PricingEngineApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "PricingEngineApiError";
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
    throw new PricingEngineApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------- API -------------------------------------------------------------

export const pricingEngineApi = {
  bulkPublish: (payload: BulkPublishPayload): Promise<BulkPublishResult> =>
    authedFetch<BulkPublishResult>(`/api/v1/pricing/prices/bulk-publish`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  /**
   * Recálculo single/masivo. `dry_run=true` retorna `RecalcPreview` (no encola
   * job); `dry_run=false` retorna `RecalcResult` con `task_id`.
   */
  recalculate: (payload: RecalcPayload): Promise<RecalcResult | RecalcPreview> =>
    authedFetch<RecalcResult | RecalcPreview>(
      `/api/v1/pricing/prices/recalculate`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),

  /** Polling del progreso de un job (recalc/bulk-publish). */
  taskProgress: (taskId: string): Promise<ProgressEvent> =>
    authedFetch<ProgressEvent>(
      `/api/v1/pricing/tasks/${encodeURIComponent(taskId)}/progress`,
    ),

  /** Revise con counter-amount + reason. Re-export del cliente Wave 2. */
  revise: (
    id: string,
    newAmount: string,
    reason: string,
  ): Promise<unknown> =>
    authedFetch(`/api/v1/pricing/prices/${id}/revise`, {
      method: "POST",
      body: JSON.stringify({ new_amount: newAmount, reason }),
    }),
};

export function isRecalcPreview(
  resp: RecalcResult | RecalcPreview,
): resp is RecalcPreview {
  return (resp as RecalcPreview).total_proposals !== undefined;
}
