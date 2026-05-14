"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/products/{sku}/ficha-enrich/*`.
 *
 * Endpoints:
 *  - POST /api/v1/products/{sku}/ficha-enrich/preview   multipart (file)
 *      → FichaEnrichPreviewResponse
 *  - POST /api/v1/products/{sku}/ficha-enrich/apply     JSON
 *      → FichaEnrichApplyResponse
 */

export interface ExtractedScalars {
  family?: string | null;
  subfamily?: string | null;
  type?: string | null;
  material?: string | null;
  dn?: string | null;
  pn?: string | null;
  connection?: string | null;
  brand?: string | null;
  weight?: number | null;
  weight_unit?: string | null;
  temp_min_c?: number | null;
  temp_max_c?: number | null;
  pressure_max_bar?: number | null;
  size?: string | null;
  [key: string]: unknown;
}

export interface ExtractedSpecs {
  seat_material?: string | null;
  seal_material?: string | null;
  stem_material?: string | null;
  standards?: string[];
  certifications?: string[];
  no_frost?: boolean | null;
  actuation_type?: string | null;
  bore_type?: string | null;
  extra?: Record<string, unknown>;
}

export interface ExtractedMaterial {
  component: string;
  position: number;
  material: string;
  observations?: string | null;
}

export interface ExtractedDimensionRow {
  dn_label: string;
  values: Record<string, number | string>;
}

export interface ExtractedTranslation {
  lang: string;
  name?: string | null;
  description?: string | null;
}

export interface PageClassification {
  page_index: number;
  kind: string;
  confidence: number;
  description: string;
}

export interface ExtractedAsset {
  page_index: number;
  asset_kind: string;
  storage_path: string;
  mime_type: string;
  description: string;
}

export interface FichaExtractionResult {
  scalars: ExtractedScalars;
  specs: ExtractedSpecs;
  materials: ExtractedMaterial[];
  dimensions: ExtractedDimensionRow[];
  translations: ExtractedTranslation[];
  page_classifications: PageClassification[];
  extracted_assets: ExtractedAsset[];
  pt_curve_points: Record<string, number>[];
  model_gaps: string[];
  confidence: number;
  raw_text_preview: string;
}

export interface FieldDiff {
  field_name: string;
  current_value: unknown;
  extracted_value: unknown;
  has_change: boolean;
  validation_error?: string | null;
}

export interface SkuDiffResult {
  sku: string;
  diffs: FieldDiff[];
}

export interface SkuApplyResult {
  sku: string;
  applied_fields: string[];
  skipped_fields: string[];
  warnings: string[];
}

export interface FichaEnrichPreviewResponse {
  sku: string;
  series: string;               // prefijo de serie, ej. "4097"
  filename: string;
  extraction: FichaExtractionResult;
  series_skus: SkuDiffResult[]; // un entry por cada SKU de la serie
  model_gaps: string[];
  page_count: number;
  confidence: number;
}

export interface FichaEnrichApplyRequest {
  extraction: FichaExtractionResult;
  apply_to_skus: string[];       // SKUs a aplicar
  apply_scalars?: boolean;
  apply_specs?: boolean;
  apply_materials?: boolean;
  apply_dimensions?: boolean;
  apply_translations?: boolean;
  apply_assets?: boolean;
  apply_pt_curve?: boolean;
  selected_scalar_fields?: string[];
}

export interface FichaEnrichApplyResponse {
  series: string;
  results: SkuApplyResult[];     // un entry por SKU aplicado
}

export class FichaEnrichApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "FichaEnrichApiError";
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
  if (
    !headers.has("Content-Type") &&
    init.body &&
    !(init.body instanceof FormData)
  ) {
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
    throw new FichaEnrichApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function previewFichaEnrich(
  sku: string,
  file: File,
): Promise<FichaEnrichPreviewResponse> {
  const fd = new FormData();
  fd.append("file", file);
  return authedFetch<FichaEnrichPreviewResponse>(
    `/api/v1/products/${encodeURIComponent(sku)}/ficha-enrich/preview`,
    { method: "POST", body: fd },
  );
}

export async function applyFichaEnrich(
  sku: string,
  body: FichaEnrichApplyRequest,
): Promise<FichaEnrichApplyResponse> {
  return authedFetch<FichaEnrichApplyResponse>(
    `/api/v1/products/${encodeURIComponent(sku)}/ficha-enrich/apply`,
    { method: "POST", body: JSON.stringify(body) },
  );
}
