"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/imports/costs/*` (US-1A-06-02 — Sprint 3).
 *
 * Endpoints (espejo del wizard PIM):
 *   POST /api/v1/imports/costs/preview      multipart/form-data (file)
 *     → { run_id, summary, orphans, samples }
 *   POST /api/v1/imports/costs/{id}/apply
 *   GET  /api/v1/imports/costs/{id}/status
 *   GET  /api/v1/imports/costs/{id}/report
 */

// ---- Types ----------------------------------------------------------------
export type ImportCostsStatus =
  | "preview_ready"
  | "applying"
  | "completed"
  | "completed_with_errors"
  | "failed";

export interface ImportCostsOrphans {
  sku_not_in_pim: string[];
  scheme_unknown: string[];
  supplier_unknown: string[];
}

export interface ImportCostsSummary {
  total: number;
  create: number;
  update: number;
  no_change: number;
  orphan: number;
  error: number;
  orphans?: {
    sku_not_in_pim: number;
    scheme_unknown: number;
    supplier_unknown: number;
  };
  applied_created?: number;
  applied_updated?: number;
  applied_errors?: number;
  applied_errors_fx_missing?: number;
}

export interface ImportCostsApplyDetails {
  total_rows: number;
  created: number;
  updated: number;
  no_change: number;
  orphans: number;
  errors: number;
  errors_fx_missing: number;
  started_at: string | null;
  finished_at: string | null;
  failure_details: Array<{
    row_index: number;
    sku: string | null;
    code: string;
    message: string;
  }>;
}

export interface ImportCostsRun {
  run_id: string;
  kind: "costs";
  filename: string;
  status: ImportCostsStatus;
  created_at: string;
  summary: ImportCostsSummary;
  orphans: ImportCostsOrphans;
  apply: ImportCostsApplyDetails | null;
  error: string | null;
}

export interface ImportCostsPreview extends ImportCostsRun {
  samples: Record<string, unknown[]>;
}

// ---- Internals ------------------------------------------------------------
export class ImportsCostsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ImportsCostsApiError";
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
  if (
    !headers.has("Content-Type") &&
    init.body &&
    !(init.body instanceof FormData)
  ) {
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
    throw new ImportsCostsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- API ------------------------------------------------------------------
export const importsCostsApi = {
  preview: (file: File): Promise<ImportCostsPreview> => {
    const fd = new FormData();
    fd.append("file", file);
    return authedFetch<ImportCostsPreview>(`/api/v1/imports/costs/preview`, {
      method: "POST",
      body: fd,
    });
  },
  apply: (runId: string): Promise<ImportCostsRun> =>
    authedFetch<ImportCostsRun>(`/api/v1/imports/costs/${runId}/apply`, {
      method: "POST",
      body: JSON.stringify({ confirm: true }),
    }),
  status: (runId: string): Promise<ImportCostsRun> =>
    authedFetch<ImportCostsRun>(`/api/v1/imports/costs/${runId}/status`),
};

export const COSTS_NON_TERMINAL: ReadonlySet<ImportCostsStatus> =
  new Set<ImportCostsStatus>(["applying"]);
export const COSTS_TERMINAL: ReadonlySet<ImportCostsStatus> =
  new Set<ImportCostsStatus>([
    "preview_ready",
    "completed",
    "completed_with_errors",
    "failed",
  ]);
