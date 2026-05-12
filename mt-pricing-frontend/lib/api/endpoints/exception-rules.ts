"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/exception-rules` (US-1B-02-02).
 *
 * Endpoints:
 *  - GET  /api/v1/exception-rules            (prices:read)
 *  - POST /api/v1/exception-rules            (prices:approve — gerente/admin)
 *  - PATCH /api/v1/exception-rules/:id/activate (prices:approve)
 *  - GET  /api/v1/exception-rules/history    (prices:read)
 */

export interface ExceptionRuleRow {
  id: string;
  code: string;
  description: string | null;
  channel_id: string | null;
  scheme_code: string | null;
  margin_threshold_pct: string | null;
  fx_swing_threshold_pct: string | null;
  min_margin_pct: string | null;
  active: boolean;
  version: number;
  effective_from: string | null;
  effective_to: string | null;
  created_by: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ExceptionRuleCreatePayload {
  code: string;
  description?: string | null;
  channel_id?: string | null;
  scheme_code?: string | null;
  margin_threshold_pct?: string | number | null;
  fx_swing_threshold_pct?: string | number | null;
  min_margin_pct?: string | number | null;
}

export class ExceptionRulesApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  public readonly code: string | null;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ExceptionRulesApiError";
    this.status = status;
    this.detail = detail;
    let code: string | null = null;
    if (detail && typeof detail === "object" && "detail" in detail) {
      const inner = (detail as { detail?: unknown }).detail;
      if (inner && typeof inner === "object" && "code" in inner) {
        const c = (inner as { code?: unknown }).code;
        if (typeof c === "string") code = c;
      }
    }
    this.code = code;
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
    throw new ExceptionRulesApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const exceptionRulesApi = {
  listActive: (): Promise<ExceptionRuleRow[]> =>
    authedFetch<ExceptionRuleRow[]>("/api/v1/exception-rules"),

  listHistory: (limit = 50): Promise<ExceptionRuleRow[]> =>
    authedFetch<ExceptionRuleRow[]>(`/api/v1/exception-rules/history?limit=${limit}`),

  create: (payload: ExceptionRuleCreatePayload): Promise<ExceptionRuleRow> =>
    authedFetch<ExceptionRuleRow>("/api/v1/exception-rules", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  activate: (ruleId: string): Promise<ExceptionRuleRow> =>
    authedFetch<ExceptionRuleRow>(`/api/v1/exception-rules/${ruleId}/activate`, {
      method: "PATCH",
    }),
};
