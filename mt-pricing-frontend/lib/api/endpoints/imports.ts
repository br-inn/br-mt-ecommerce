"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/imports` (US-1A-06-01 PIM importer).
 *
 * Contrato confirmado por backend (Agente 2):
 *  - POST /api/v1/imports/preview      multipart/form-data (file + type=pim)
 *      → { run_id, status, summary?, ... }
 *  - POST /api/v1/imports/{id}/apply
 *  - GET  /api/v1/imports/{id}/status  → { status, progress, summary }
 *  - GET  /api/v1/imports/{id}/report  → ImportReport
 */

// ---- Types ----------------------------------------------------------------

export type ImportStatus =
  | "queued"
  | "parsing"
  | "preview_ready"
  | "applying"
  | "completed"
  | "failed"
  | "cancelled";

export interface ImportRowDiff {
  field: string;
  before: unknown;
  after: unknown;
  /** `true` si el field está en `manual_locked_fields`. */
  locked?: boolean;
}

export interface ImportRow {
  row_index: number;
  sku: string;
  /** Server emite uno de estos. `skip_locked` aparece cuando todos los cambios están bloqueados. */
  action: "create" | "update" | "skip_locked" | "no_change" | "error" | "orphan";
  diff?: ImportRowDiff[] | null;
  error_code?: string | null;
  error_message?: string | null;
}

export interface ImportSummary {
  total: number;
  creates: number;
  updates: number;
  skipped_locked: number;
  no_change: number;
  errors: number;
  orphans: number;
}

export interface ImportProgress {
  /** chunks aplicados sobre total. Server lo emite durante `applying`. */
  chunks_done: number;
  chunks_total: number;
  /** rows ya commiteadas en saving (acumulado). */
  rows_done: number;
}

export interface ImportRun {
  run_id: string;
  type: "pim";
  status: ImportStatus;
  filename: string | null;
  uploaded_at: string;
  summary: ImportSummary | null;
  progress: ImportProgress | null;
  error_message?: string | null;
}

export interface ImportPreview extends ImportRun {
  /**
   * Filas materializadas (subset). El backend recorta ≤ 500 rows en preview;
   * para descarga completa se usa `/report`.
   */
  rows: ImportRow[];
}

export interface ImportReport {
  run_id: string;
  status: ImportStatus;
  summary: ImportSummary;
  rows: ImportRow[];
}

// ---- Analyze / mapping types -----------------------------------------------

export interface ColumnMappingItem {
  excel_col: string;
  target_field: string;
  transform: string;
  confidence: number;
  notes?: string;
}

export interface AnalyzeImportResponse {
  filename: string;
  detected_header_row: number;
  headers: string[];
  /** Hasta 5 filas de datos de muestra (valores como string|null). */
  sample_rows: (string | null)[][];
  proposed_mapping: ColumnMappingItem[];
}

// ---- Internals ------------------------------------------------------------

export class ImportsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ImportsApiError";
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
    throw new ImportsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---- API ------------------------------------------------------------------

export const importsApi = {
  /** Detecta estructura del xlsx y propone mapeo de columnas via LLM. */
  analyze: (file: File): Promise<AnalyzeImportResponse> => {
    const fd = new FormData();
    fd.append("file", file);
    return authedFetch<AnalyzeImportResponse>(`/api/v1/imports/analyze`, {
      method: "POST",
      body: fd,
    });
  },
  /** Sube xlsx en modo preview. Devuelve `run_id` y status inicial. */
  preview: (
    file: File,
    type: "pim" = "pim",
    mapping?: ColumnMappingItem[],
  ): Promise<ImportPreview> => {
    const fd = new FormData();
    fd.append("file", file);
    fd.append("type", type);
    if (mapping) fd.append("mapping_json", JSON.stringify(mapping));
    return authedFetch<ImportPreview>(`/api/v1/imports/preview`, {
      method: "POST",
      body: fd,
    });
  },
  /** Confirma y aplica los cambios calculados en preview.
   *
   * Stage 3 (Wave 11): permite override per-run de divisiones a asignar a los
   * SKUs creados/actualizados. Si vacío, el backend usa
   * `settings.PIM_DEFAULT_DIVISIONS`.
   */
  apply: (
    runId: string,
    options: { chunk_size?: number; division_codes?: string[] | null } = {},
  ): Promise<ImportRun> => {
    const body: Record<string, unknown> = {};
    if (options.chunk_size !== undefined) body.chunk_size = options.chunk_size;
    if (options.division_codes !== undefined && options.division_codes !== null) {
      body.division_codes = options.division_codes;
    }
    return authedFetch<ImportRun>(`/api/v1/imports/${runId}/apply`, {
      method: "POST",
      ...(Object.keys(body).length > 0 ? { body: JSON.stringify(body) } : {}),
    });
  },
  /** Polling de status durante parsing/applying. */
  status: (runId: string): Promise<ImportRun> =>
    authedFetch<ImportRun>(`/api/v1/imports/${runId}/status`),
  /** Reporte final (post-completed). */
  report: (runId: string): Promise<ImportReport> =>
    authedFetch<ImportReport>(`/api/v1/imports/${runId}/report`),
  /** Devuelve el preview enriquecido con rows muestreadas. */
  getPreview: (runId: string): Promise<ImportPreview> =>
    authedFetch<ImportPreview>(`/api/v1/imports/${runId}`),
};

/** Status que aún no son terminales — el polling sigue activo. */
export const NON_TERMINAL_STATUSES: ReadonlySet<ImportStatus> = new Set<ImportStatus>([
  "queued",
  "parsing",
  "applying",
]);

/** Status terminales — apaga el polling. */
export const TERMINAL_STATUSES: ReadonlySet<ImportStatus> = new Set<ImportStatus>([
  "preview_ready",
  "completed",
  "failed",
  "cancelled",
]);
