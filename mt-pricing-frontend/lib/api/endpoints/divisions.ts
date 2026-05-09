"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/divisions` y `/api/v1/admin/divisions`
 * (Stage 3 / Wave 11 — taxonomía).
 *
 * Endpoints:
 *  - GET    /api/v1/divisions                              (products:read)
 *  - GET    /api/v1/admin/divisions                        (admin:taxonomy)
 *  - POST   /api/v1/admin/divisions                        (admin:taxonomy)
 *  - PATCH  /api/v1/admin/divisions/{id}                   (admin:taxonomy)
 *  - DELETE /api/v1/admin/divisions/{id}                   (admin:taxonomy)
 */

export interface Division {
  id: string;
  code: string;
  name: string;
  description: string | null;
  sort_order: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface DivisionCreatePayload {
  code: string;
  name: string;
  description?: string | null;
  sort_order?: number;
  active?: boolean;
}

export interface DivisionPatchPayload {
  name?: string | null;
  description?: string | null;
  sort_order?: number | null;
  active?: boolean | null;
}

export class DivisionsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "DivisionsApiError";
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
    throw new DivisionsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const divisionsApi = {
  /** Listado público (solo activas). */
  listPublic: (): Promise<Division[]> =>
    authedFetch<Division[]>(`/api/v1/divisions`),
  /** Listado admin (incluye inactivas). */
  list: (): Promise<Division[]> =>
    authedFetch<Division[]>(`/api/v1/admin/divisions`),
  create: (payload: DivisionCreatePayload): Promise<Division> =>
    authedFetch<Division>(`/api/v1/admin/divisions`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patch: (id: string, payload: DivisionPatchPayload): Promise<Division> =>
    authedFetch<Division>(`/api/v1/admin/divisions/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  remove: (id: string): Promise<void> =>
    authedFetch<void>(`/api/v1/admin/divisions/${id}`, { method: "DELETE" }),
};
