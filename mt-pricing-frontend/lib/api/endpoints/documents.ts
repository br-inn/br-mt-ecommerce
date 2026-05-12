"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import { ProductsApiError } from "./products";
import type {
  Document,
  DocumentCreatePayload,
  DocumentListFilters,
  DocumentPatchPayload,
} from "../types-assets-extended";

/**
 * Wrappers tipados para endpoints Fase 4 de documentos controlados.
 */

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
    throw new ProductsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    search.set(k, String(v));
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const documentsApi = {
  list: (filters: DocumentListFilters = {}): Promise<Document[]> =>
    authedFetch<Document[]>(
      `/api/v1/documents${buildQuery({
        type: filters.type,
        language: filters.language,
      })}`,
    ),

  get: (id: string): Promise<Document> =>
    authedFetch<Document>(`/api/v1/documents/${id}`),

  create: (payload: DocumentCreatePayload): Promise<Document> =>
    authedFetch<Document>(`/api/v1/admin/documents`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  patch: (id: string, payload: DocumentPatchPayload): Promise<Document> =>
    authedFetch<Document>(`/api/v1/admin/documents/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  remove: (id: string): Promise<void> =>
    authedFetch<void>(`/api/v1/admin/documents/${id}`, {
      method: "DELETE",
    }),
};
