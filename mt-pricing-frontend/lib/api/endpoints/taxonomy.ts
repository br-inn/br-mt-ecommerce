"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente público de la taxonomía (Stage 1 Opción C):
 *
 *  GET /api/v1/taxonomy/tree   →  families · subfamilies · product_types
 *
 * Cacheable (staleTime 5+ min); las hojas son códigos snake_case con
 * `name` en español/inglés displayable.
 */

export interface TaxonomyType {
  id: string;
  code: string;
  name: string;
  description: string | null;
  sort_order: number;
  active: boolean;
}

export interface TaxonomySubfamily extends TaxonomyType {
  family_id: string;
  types: TaxonomyType[];
}

export interface TaxonomyFamily {
  id: string;
  code: string;
  name: string;
  description: string | null;
  sort_order: number;
  active: boolean;
  subfamilies: TaxonomySubfamily[];
}

export interface TaxonomyTreeResponse {
  families: TaxonomyFamily[];
}

async function authedFetch<T>(path: string): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers();
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  const res = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}${path}`, {
    headers,
    cache: "no-store",
  });
  if (!res.ok) throw new Error(`taxonomy fetch failed: HTTP ${res.status}`);
  return (await res.json()) as T;
}

export const taxonomyApi = {
  tree: (): Promise<TaxonomyTreeResponse> =>
    authedFetch<TaxonomyTreeResponse>("/api/v1/taxonomy/tree"),
};
