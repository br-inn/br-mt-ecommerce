"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

export type ScraperSourceStatus = "draft" | "testing" | "active" | "disabled" | "degraded";
export type FetchMode = "static" | "headless" | "stealth";
export type DestinationProfile = "competitor_price" | "product_data";
export type ValidationStatus = "unvalidated" | "passing" | "failing";

export interface ScraperSourceRead {
  id: string;
  name: string;
  slug: string;
  base_url: string;
  description: string | null;
  destination_profile: DestinationProfile;
  fetch_mode: FetchMode;
  status: ScraperSourceStatus;
  competitor_brand_id: string | null;
  created_at: string;
  updated_at: string;
}

export interface ScraperSourceCreate {
  name: string;
  slug: string;
  base_url: string;
  destination_profile: DestinationProfile;
  fetch_mode: FetchMode;
  description?: string | null;
}

export interface ScraperSourceUpdate {
  name?: string;
  base_url?: string;
  description?: string | null;
  destination_profile?: DestinationProfile;
  fetch_mode?: FetchMode;
  status?: ScraperSourceStatus;
}

export interface RecipeRead {
  id: string;
  source_id: string;
  version: number;
  is_live: boolean;
  validation_status: ValidationStatus;
  has_unapproved_snippet: boolean;
  recipe: Record<string, unknown>;
  created_at: string;
}

export interface RecipeCreate {
  recipe: Record<string, unknown>;
}

export interface ValidateRequest {
  recipe_id: string;
  test_url: string;
}

export interface ValidateResponse {
  status: string;
  field_results: Record<string, string>;
  records: Record<string, unknown>[];
}

export interface ActivateRequest {
  recipe_id: string;
}

export interface RecipeTransformDef {
  op: "regex_capture" | "strip_currency" | "replace" | "map_values" | "unit_factor";
  pattern?: string;
  find?: string;
  replace_with?: string;
  mapping?: Record<string, string>;
  factor?: number;
}

export interface RecipeFieldDef {
  name: string;
  selector: string;
  extract: string;
  type: "str" | "float" | "int" | "currency" | "bool";
  transform: RecipeTransformDef | null;
}

export interface AnalyzeRequest {
  url: string;
  context?: string | null;
  hint?: string | null;
}

export interface AnalyzeResponse {
  detected_mode: "static" | "headless" | "stealth";
  proposed_source: {
    name: string;
    slug: string;
    base_url: string;
  };
  proposed_recipe: {
    url_templates: { search?: string; pdp?: string; list?: string; product?: string };
    list_item_selector: string | null;
    fields: RecipeFieldDef[];
    anti_bot_hints?: Record<string, unknown>;
  };
  field_confidence: Record<string, number>;
  preview_records: Record<string, unknown>[];
  missing_required: string[];
  warnings: string[];
}

export class ScraperSourcesApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ScraperSourcesApiError";
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
    throw new ScraperSourcesApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const scraperSourcesApi = {
  list: (): Promise<ScraperSourceRead[]> =>
    authedFetch<ScraperSourceRead[]>("/api/v1/scraper-sources"),

  create: (req: ScraperSourceCreate): Promise<ScraperSourceRead> =>
    authedFetch<ScraperSourceRead>("/api/v1/scraper-sources", {
      method: "POST",
      body: JSON.stringify(req),
    }),

  update: (id: string, req: ScraperSourceUpdate): Promise<ScraperSourceRead> =>
    authedFetch<ScraperSourceRead>(`/api/v1/scraper-sources/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(req),
    }),

  listRecipes: (sourceId: string): Promise<RecipeRead[]> =>
    authedFetch<RecipeRead[]>(
      `/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/recipes`,
    ),

  createRecipe: (sourceId: string, req: RecipeCreate): Promise<RecipeRead> =>
    authedFetch<RecipeRead>(
      `/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/recipes`,
      {
        method: "POST",
        body: JSON.stringify(req),
      },
    ),

  validate: (sourceId: string, req: ValidateRequest): Promise<ValidateResponse> =>
    authedFetch<ValidateResponse>(
      `/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/validate`,
      {
        method: "POST",
        body: JSON.stringify(req),
      },
    ),

  activate: (sourceId: string, req: ActivateRequest): Promise<ScraperSourceRead> =>
    authedFetch<ScraperSourceRead>(
      `/api/v1/scraper-sources/${encodeURIComponent(sourceId)}/activate`,
      {
        method: "POST",
        body: JSON.stringify(req),
      },
    ),

  analyze: (req: AnalyzeRequest): Promise<AnalyzeResponse> =>
    authedFetch<AnalyzeResponse>("/api/v1/scraper-sources/analyze", {
      method: "POST",
      body: JSON.stringify(req),
    }),
};
