"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/admin/pim/data-quality`.
 *
 * Endpoint:
 *  - GET  /api/v1/admin/pim/data-quality  → snapshot de calidad del catálogo PIM
 *
 * RBAC: requiere `admin:read`.
 */

export interface PimGap {
  count: number;
  pct: number;
  sample_skus: string[];
}

export interface PimDataQualityReport {
  generated_at: string;
  total_skus: number;
  gaps: {
    missing_name_en: PimGap;
    missing_specs: PimGap;
    missing_images: PimGap;
    missing_brand: PimGap;
    missing_family: PimGap;
    specs_below_threshold: PimGap;
  };
}

export class AdminPimApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "AdminPimApiError";
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
    throw new AdminPimApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const adminPimApi = {
  getDataQuality: (): Promise<PimDataQualityReport> =>
    authedFetch<PimDataQualityReport>(`/api/v1/admin/pim/data-quality`),
};
