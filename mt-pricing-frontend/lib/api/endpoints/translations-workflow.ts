"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

import type { Language } from "@/lib/api/endpoints/products";

/**
 * Endpoints del Translations Approval Workflow (US-1A-02-05).
 *
 * Vive en su propio módulo para no acoplar el cliente clásico de products
 * (que ya quedó congelado en S2). Los hooks de React Query consumen estos
 * wrappers desde `lib/hooks/products/use-translation-workflow.ts`.
 */

export type TranslationWorkflowStatus =
  | "draft"
  | "pending"
  | "pending_review"
  | "approved"
  | "stale";

export interface TranslationWorkflowRow {
  sku: string;
  lang: Language;
  name: string | null;
  description: string | null;
  marketing_copy: string | null;
  status: TranslationWorkflowStatus;
  translated_by: string | null;
  translated_at: string | null;
  reviewed_by: string | null;
  reviewed_at: string | null;
  staleness_reason: string | null;
  rejection_reason: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarkStaleResponse {
  sku: string;
  affected_count: number;
  affected: TranslationWorkflowRow[];
}

export interface RejectPayload {
  reason: string;
}

export interface MarkStalePayload {
  reason?: string;
}

class WorkflowApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "WorkflowApiError";
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
    throw new WorkflowApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const translationsWorkflowApi = {
  requestReview: (sku: string, lang: Language): Promise<TranslationWorkflowRow> =>
    authedFetch<TranslationWorkflowRow>(
      `/api/v1/products/${sku}/translations/${lang}/request-review`,
      { method: "POST" },
    ),
  reject: (
    sku: string,
    lang: Language,
    payload: RejectPayload,
  ): Promise<TranslationWorkflowRow> =>
    authedFetch<TranslationWorkflowRow>(
      `/api/v1/products/${sku}/translations/${lang}/reject`,
      {
        method: "POST",
        body: JSON.stringify(payload),
      },
    ),
  markStale: (sku: string, payload: MarkStalePayload = {}): Promise<MarkStaleResponse> =>
    authedFetch<MarkStaleResponse>(
      `/api/v1/products/${sku}/translations/mark-stale`,
      {
        method: "POST",
        body: JSON.stringify({ reason: payload.reason ?? "master_en_changed" }),
      },
    ),
};

export { WorkflowApiError };
