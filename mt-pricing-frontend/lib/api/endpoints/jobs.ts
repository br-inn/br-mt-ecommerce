"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/admin/jobs/*` (DatabaseScheduler editable).
 *
 * Backend contracts en `mt-pricing-backend/app/api/routes/jobs.py`.
 */

// ---- Types ----------------------------------------------------------------

export type JobOwner = "infra" | "business";
export type ScheduleType = "cron" | "interval";
export type JobStatus =
  | "idle"
  | "running"
  | "success"
  | "failure"
  | "cancelled";

export interface JobDefinitionListItem {
  id: string;
  code: string;
  task_name: string;
  description: string | null;
  owner: JobOwner;
  schedule_type: ScheduleType;
  cron_expression: string | null;
  interval_seconds: number | null;
  timezone: string;
  queue: string;
  enabled: boolean;
  last_run_at: string | null;
  next_run_at: string | null;
  last_status: JobStatus | null;
}

export interface JobDefinitionDetail extends JobDefinitionListItem {
  args: unknown[];
  kwargs: Record<string, unknown>;
  last_error: string | null;
  last_celery_task_id: string | null;
  edited_by: string | null;
  edited_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface JobDefinitionCreatePayload {
  code: string;
  task_name: string;
  description?: string | null | undefined;
  owner?: JobOwner | undefined;
  schedule_type: ScheduleType;
  cron_expression?: string | null | undefined;
  interval_seconds?: number | null | undefined;
  timezone?: string | undefined;
  queue?: string | undefined;
  args?: unknown[] | undefined;
  kwargs?: Record<string, unknown> | undefined;
  enabled?: boolean | undefined;
}

export interface JobDefinitionUpdatePayload {
  description?: string | null | undefined;
  cron_expression?: string | null | undefined;
  interval_seconds?: number | null | undefined;
  queue?: string | undefined;
  args?: unknown[] | undefined;
  kwargs?: Record<string, unknown> | undefined;
  enabled?: boolean | undefined;
}

export interface JobRun {
  id: string;
  job_id: string;
  job_code: string;
  status: JobStatus;
  started_at: string | null;
  finished_at: string | null;
  retries: number;
  celery_task_id: string | null;
  result: Record<string, unknown> | null;
  error: string | null;
  created_at: string;
  duration_ms: number | null;
}

export interface JobRunsPage {
  items: JobRun[];
  count: number;
  next_cursor: string | null;
}

export interface JobRunNowResponse {
  job_id: string;
  run_id: string;
  celery_task_id: string | null;
  enqueued_at: string;
}

// ---- Internals ------------------------------------------------------------

export class JobsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "JobsApiError";
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
    throw new JobsApiError(res.status, detail, res.statusText);
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

export const jobsAdminApi = {
  list: (params: {
    enabled?: boolean | undefined;
    owner?: JobOwner | undefined;
    limit?: number | undefined;
    offset?: number | undefined;
  } = {}) =>
    authedFetch<JobDefinitionListItem[]>(
      `/api/v1/admin/jobs${buildQuery(params)}`,
    ),
  get: (id: string) =>
    authedFetch<JobDefinitionDetail>(`/api/v1/admin/jobs/${id}`),
  create: (payload: JobDefinitionCreatePayload) =>
    authedFetch<JobDefinitionDetail>(`/api/v1/admin/jobs`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: JobDefinitionUpdatePayload) =>
    authedFetch<JobDefinitionDetail>(`/api/v1/admin/jobs/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  runNow: (id: string) =>
    authedFetch<JobRunNowResponse>(`/api/v1/admin/jobs/${id}/run-now`, {
      method: "POST",
    }),
  listRuns: (
    id: string,
    params: { limit?: number | undefined; offset?: number | undefined } = {},
  ) =>
    authedFetch<JobRunsPage>(
      `/api/v1/admin/jobs/${id}/runs${buildQuery(params)}`,
    ),
};
