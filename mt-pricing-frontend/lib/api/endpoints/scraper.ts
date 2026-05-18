"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/scraper` — Amazon UAE price scraper.
 *
 * Endpoints (Wave 1 backend):
 *  - POST  /api/v1/scraper/run           { skus, force }  → { job_id, total }
 *  - GET   /api/v1/scraper/job/{job_id}                   → ScrapeJobStatus
 *
 * Permisos: products:write para POST, products:read para GET.
 */

export interface ScrapeRunRequest {
  skus: string[];
  force: boolean;
}

export interface ScrapeRunResponse {
  job_id: string;
  total: number;
}

export type ScrapeJobStatusValue =
  | "pending"
  | "running"
  | "completed"
  | "failed";

export interface ScrapeJobStatus {
  job_id: string;
  status: ScrapeJobStatusValue;
  total: number;
  completed: number;
  failed: number;
}

export class ScraperApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ScraperApiError";
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
    throw new ScraperApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const scraperApi = {
  run: (req: ScrapeRunRequest): Promise<ScrapeRunResponse> =>
    authedFetch<ScrapeRunResponse>("/api/v1/scraper/run", {
      method: "POST",
      body: JSON.stringify(req),
    }),
  getJob: (jobId: string): Promise<ScrapeJobStatus> =>
    authedFetch<ScrapeJobStatus>(`/api/v1/scraper/job/${encodeURIComponent(jobId)}`),
};
