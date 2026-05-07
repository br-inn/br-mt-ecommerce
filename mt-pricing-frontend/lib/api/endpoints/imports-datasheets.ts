"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/imports/datasheets/*` (US-1A-06-04 Sprint 4).
 *
 * Endpoints (Agente B Sprint 4):
 *  - POST /api/v1/imports/datasheets/preview       multipart (file, sku?)
 *      → { run_id, kind: 'datasheets', preview }
 *  - POST /api/v1/imports/datasheets/{run_id}/apply
 *      → DatasheetsRun
 *  - GET  /api/v1/imports/datasheets/{run_id}/status
 *      → DatasheetsRun
 *  - GET  /api/v1/products/{sku}/datasheets
 *      → DatasheetSummary[]
 */

export type DatasheetKind = "ficha_tecnica" | "compliance" | "manual";

export interface DatasheetExtractedSpec {
  field: string;
  value: string;
  confidence: number;
  source_page?: number | null;
}

export interface DatasheetPreviewItem {
  filename: string;
  detected_kind: DatasheetKind | null;
  matched_skus: string[];
  orphan_reason: string | null;
  page_count: number;
  size_bytes: number;
  extracted_specs: DatasheetExtractedSpec[];
}

export interface DatasheetsPreviewBody {
  run_id: string;
  total_files: number;
  matched: number;
  orphans: number;
  items: DatasheetPreviewItem[];
}

export type DatasheetsRunStatus =
  | "preview_ready"
  | "applying"
  | "completed"
  | "completed_with_errors"
  | "failed";

export interface DatasheetsRun {
  run_id: string;
  kind: "datasheets";
  status: DatasheetsRunStatus;
  created_at: string;
  preview: DatasheetsPreviewBody;
  applied?: {
    persisted: number;
    errors: number;
    failed_filenames: string[];
  } | null;
  error?: string | null;
}

export interface DatasheetSummary {
  id: string;
  kind: DatasheetKind;
  storage_path: string;
  signed_url: string;
  signed_url_expires_at: string;
  original_filename: string;
  file_size_bytes: number;
  page_count: number | null;
  uploaded_at: string;
  uploaded_by: string | null;
}

export class ImportsDatasheetsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ImportsDatasheetsApiError";
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
    throw new ImportsDatasheetsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const importsDatasheetsApi = {
  preview: (file: File, sku?: string): Promise<DatasheetsRun> => {
    const fd = new FormData();
    fd.append("file", file);
    if (sku) fd.append("sku", sku);
    return authedFetch<DatasheetsRun>(
      `/api/v1/imports/datasheets/preview`,
      { method: "POST", body: fd },
    );
  },
  apply: (runId: string): Promise<DatasheetsRun> =>
    authedFetch<DatasheetsRun>(
      `/api/v1/imports/datasheets/${encodeURIComponent(runId)}/apply`,
      { method: "POST", body: JSON.stringify({ confirm: true }) },
    ),
  status: (runId: string): Promise<DatasheetsRun> =>
    authedFetch<DatasheetsRun>(
      `/api/v1/imports/datasheets/${encodeURIComponent(runId)}/status`,
    ),
  listForSku: (sku: string): Promise<DatasheetSummary[]> =>
    authedFetch<DatasheetSummary[]>(
      `/api/v1/products/${encodeURIComponent(sku)}/datasheets`,
    ),
};

export const DATASHEETS_NON_TERMINAL: ReadonlySet<DatasheetsRunStatus> =
  new Set<DatasheetsRunStatus>(["applying"]);
