"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para las **rutas batch** de imports (DB-backed ImportRun).
 *
 * El módulo `imports.ts` original cubre el wizard sincrono in-memory
 * (preview/apply). Este cubre la cola Celery + persistencia:
 *  - GET  /api/v1/imports/runs        — listado paginado con filtros.
 *  - GET  /api/v1/imports/runs/{id}   — detalle (counters + errors[]).
 *  - POST /api/v1/imports/pim/upload  — sube xlsx + dispara Celery.
 *  - POST /api/v1/imports/pim/run-from-fixture (dev only).
 */

// ---- Types ----------------------------------------------------------------

export type ImportRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type ImportType = "pim" | "costs" | "datasheets";

export interface ImportRunError {
  row: number;
  error: string;
  sku?: string | null;
  field?: string | null;
}

export interface ImportRunRow {
  run_id: string;
  import_type: ImportType;
  source_filename: string | null;
  source_storage_path: string | null;
  status: ImportRunStatus;
  total_rows: number | null;
  inserted_rows: number | null;
  updated_rows: number | null;
  skipped_rows: number | null;
  error_rows: number | null;
  errors: ImportRunError[];
  errors_total: number;
  summary: Record<string, unknown>;
  started_at: string | null;
  finished_at: string | null;
  created_at: string;
  triggered_by: string | null;
  celery_task_id: string | null;
}

export interface ImportRunsPage {
  items: ImportRunRow[];
  count: number;
}

export interface UploadResponse {
  run_id: string;
  status: ImportRunStatus;
  celery_task_id: string | null;
  source_storage_path: string;
}

export interface RunFromFixtureResponse {
  run_id: string;
  status: ImportRunStatus;
  celery_task_id: string | null;
  source_path: string;
}

// ---- Internals ------------------------------------------------------------

export class ImportsAdminApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ImportsAdminApiError";
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
  if (!headers.has("Content-Type") && init.body && !(init.body instanceof FormData)) {
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
    throw new ImportsAdminApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null) search.set(k, String(v));
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

// ---- API ------------------------------------------------------------------

export const importsAdminApi = {
  listRuns: (params: {
    import_type?: ImportType | undefined;
    status?: ImportRunStatus | undefined;
    limit?: number | undefined;
  } = {}) =>
    authedFetch<ImportRunsPage>(`/api/v1/imports/runs${buildQuery(params)}`),
  getRun: (runId: string) =>
    authedFetch<ImportRunRow>(`/api/v1/imports/runs/${runId}`),
  uploadPim: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return authedFetch<UploadResponse>("/api/v1/imports/pim/upload", {
      method: "POST",
      body: fd,
    });
  },
  runFromFixture: () =>
    authedFetch<RunFromFixtureResponse>(
      "/api/v1/imports/pim/run-from-fixture",
      { method: "POST" },
    ),
};

/** Status terminales — el polling se apaga. */
export const TERMINAL_RUN_STATUSES: ReadonlySet<ImportRunStatus> =
  new Set<ImportRunStatus>(["completed", "completed_with_errors", "failed"]);
