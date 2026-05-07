"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/imports/materials/*` (US-1A-06-03 — Sprint 3).
 */

export type ImportMaterialsStatus =
  | "preview_ready"
  | "applying"
  | "completed"
  | "completed_with_errors"
  | "failed";

export type ImportMaterialsApplyMode = "replace" | "append";

export interface ImportMaterialsSummary {
  total: number;
  ok: number;
  errors: number;
  materials_columns: number;
  applied_inserted?: number;
  applied_truncated?: boolean;
  applied_errors?: number;
}

export interface ImportMaterialsApplyDetails {
  total_rows: number;
  inserted: number;
  truncated: boolean;
  errors: number;
  started_at: string | null;
  finished_at: string | null;
  failure_details: Array<{
    row_index: number;
    descriptor: string | null;
    reasons: string[];
  }>;
}

export interface ImportMaterialsPreview {
  run_id: string;
  kind: "materials";
  filename: string;
  status: ImportMaterialsStatus;
  created_at: string;
  summary: ImportMaterialsSummary;
  materials_columns: string[];
  samples: Array<{
    row_index: number;
    producto_descriptor: string | null;
    temperatura_c: string | null;
    compatibilities: Record<string, string>;
    errors: string[];
  }>;
}

export interface ImportMaterialsRun {
  run_id: string;
  kind: "materials";
  status: ImportMaterialsStatus;
  summary: ImportMaterialsSummary;
  apply: ImportMaterialsApplyDetails | null;
  error: string | null;
}

export class ImportsMaterialsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ImportsMaterialsApiError";
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
    throw new ImportsMaterialsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const importsMaterialsApi = {
  preview: (file: File): Promise<ImportMaterialsPreview> => {
    const fd = new FormData();
    fd.append("file", file);
    return authedFetch<ImportMaterialsPreview>(
      `/api/v1/imports/materials/preview`,
      { method: "POST", body: fd },
    );
  },
  apply: (
    runId: string,
    mode: ImportMaterialsApplyMode = "replace",
  ): Promise<ImportMaterialsRun> =>
    authedFetch<ImportMaterialsRun>(`/api/v1/imports/materials/${runId}/apply`, {
      method: "POST",
      body: JSON.stringify({ mode }),
    }),
  status: (runId: string): Promise<ImportMaterialsRun> =>
    authedFetch<ImportMaterialsRun>(`/api/v1/imports/materials/${runId}/status`),
};
