"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/materials` y `/api/v1/admin/materials`
 * (Stage 3 / Wave 11).
 */

export interface Material {
  id: string;
  code: string;
  name: string;
  family_kind: string | null;
  notes: string | null;
  sort_order: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface MaterialCreatePayload {
  code: string;
  name: string;
  family_kind?: string | null;
  notes?: string | null;
  sort_order?: number;
  active?: boolean;
}

export interface MaterialPatchPayload {
  name?: string | null;
  family_kind?: string | null;
  notes?: string | null;
  sort_order?: number | null;
  active?: boolean | null;
}

export class MaterialsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "MaterialsApiError";
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
    throw new MaterialsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const materialsApi = {
  listPublic: (): Promise<Material[]> =>
    authedFetch<Material[]>(`/api/v1/materials`),
  list: (): Promise<Material[]> =>
    authedFetch<Material[]>(`/api/v1/admin/materials`),
  create: (payload: MaterialCreatePayload): Promise<Material> =>
    authedFetch<Material>(`/api/v1/admin/materials`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patch: (id: string, payload: MaterialPatchPayload): Promise<Material> =>
    authedFetch<Material>(`/api/v1/admin/materials/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  remove: (id: string): Promise<void> =>
    authedFetch<void>(`/api/v1/admin/materials/${id}`, { method: "DELETE" }),
};
