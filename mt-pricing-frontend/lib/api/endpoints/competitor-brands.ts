"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/competitor-brands` — marcas competidoras.
 *
 * Endpoints:
 *  - GET    /api/v1/competitor-brands/           → CompetitorBrandRead[]
 *  - POST   /api/v1/competitor-brands/           → CompetitorBrandRead
 *  - PATCH  /api/v1/competitor-brands/{id}       → CompetitorBrandRead
 *  - POST   /api/v1/competitor-brands/run        → BrandScrapeRunResponse
 *
 * Permisos: products:write para mutaciones, products:read para lectura.
 */

export interface CompetitorBrandRead {
  id: string;
  name: string;
  amazon_search_term: string | null;
  amazon_dept: string;
  amazon_category_node: string | null;
  is_active: boolean;
  notes: string | null;
  last_scraped_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface CompetitorBrandCreate {
  name: string;
  amazon_search_term?: string | null;
  amazon_dept?: string;
  amazon_category_node?: string | null;
  is_active?: boolean;
  notes?: string | null;
}

export interface CompetitorBrandUpdate {
  name?: string;
  amazon_search_term?: string | null;
  amazon_dept?: string;
  amazon_category_node?: string | null;
  is_active?: boolean;
  notes?: string | null;
}

export interface BrandScrapeRunRequest {
  brand_ids?: string[] | null;
  force?: boolean;
}

export interface BrandScrapeRunResponse {
  job_id: string | null;
  total_brands: number;
  status: string;
}

export class CompetitorBrandsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "CompetitorBrandsApiError";
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
    throw new CompetitorBrandsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const competitorBrandsApi = {
  list: (active_only = false): Promise<CompetitorBrandRead[]> =>
    authedFetch<CompetitorBrandRead[]>(
      `/api/v1/competitor-brands/?active_only=${active_only}`,
    ),

  create: (req: CompetitorBrandCreate): Promise<CompetitorBrandRead> =>
    authedFetch<CompetitorBrandRead>("/api/v1/competitor-brands/", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  update: (id: string, req: CompetitorBrandUpdate): Promise<CompetitorBrandRead> =>
    authedFetch<CompetitorBrandRead>(`/api/v1/competitor-brands/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(req),
    }),

  run: (req: BrandScrapeRunRequest = {}): Promise<BrandScrapeRunResponse> =>
    authedFetch<BrandScrapeRunResponse>("/api/v1/competitor-brands/run", {
      method: "POST",
      body: JSON.stringify(req),
    }),
};
