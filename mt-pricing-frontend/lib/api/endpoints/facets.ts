"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export interface FacetBucket {
  value: string;
  count: number;
}

export interface TranslationLangFacet {
  approved: number;
  pending: number;
  draft: number;
  missing: number;
}

export interface FacetsResponse {
  total: number;
  total_unfiltered: number;
  family: FacetBucket[];
  subfamily?: FacetBucket[];
  type?: FacetBucket[];
  material: FacetBucket[];
  dn: FacetBucket[];
  pn: FacetBucket[];
  data_quality: Record<string, number>;
  active: Record<string, number>;
  image_status: Record<string, number>;
  has_image: Record<string, number>;
  translation_status: Record<string, TranslationLangFacet>;
  // Stage 3 (Wave 11) — taxonomy refinement facets
  division?: FacetBucket[];
  series?: FacetBucket[];
  tier_code?: FacetBucket[];
  material_curated?: FacetBucket[];
}

export interface FacetsFilters {
  family?: string | null;
  subfamily?: string | null;
  type?: string | null;
  brand?: string | null;
  material?: string | null;
  dn?: string | null;
  pn?: string | null;
  data_quality?: string | null;
  active?: boolean | null;
  image_status?: string | null;
  has_image?: boolean | null;
  lifecycle_status?: string | null;
  translation_status?: "pending" | "draft" | "approved" | null;
  translation_lang?: "es" | "ar" | null;
  q?: string | null;
  // Stage 3 — taxonomy filters
  division?: string | null;
  series_id?: string | null;
  material_id?: string | null;
  tier_code?: string | null;
}

function buildQuery(p: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(p)) {
    if (v === undefined || v === null || v === "") continue;
    search.set(k, String(v));
  }
  const s = search.toString();
  return s ? `?${s}` : "";
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
  if (!res.ok) {
    throw new Error(`facets fetch failed: HTTP ${res.status}`);
  }
  return (await res.json()) as T;
}

export const facetsApi = {
  get: (filters: FacetsFilters = {}): Promise<FacetsResponse> =>
    authedFetch<FacetsResponse>(
      `/api/v1/products/facets${buildQuery(filters as Record<string, unknown>)}`,
    ),
};
