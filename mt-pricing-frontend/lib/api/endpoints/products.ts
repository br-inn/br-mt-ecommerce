"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Wrappers tipados para endpoints `/api/v1/products`.
 *
 * TODO: regenerar `lib/api/types.ts` con `pnpm openapi:gen` y
 * tiparlos directamente desde `paths`. Mientras tanto definimos
 * shapes locales que matchean la spec OpenAPI del backend.
 */

// ---- Types ----------------------------------------------------------------

export type DataQuality = "complete" | "partial" | "blocked";
export type TranslationStatus = "draft" | "pending" | "approved";
export type Language = "es" | "ar";

export interface ProductDimensions {
  length?: number | null;
  width?: number | null;
  height?: number | null;
  unit?: "mm" | "cm" | "m" | null;
}

export interface ProductPackaging {
  qty_x_box?: number | null;
  ean_unit?: string | null;
  ean_box?: string | null;
  moq?: number | null;
}

export interface ProductIntrastat {
  hs_code?: string | null;
  origin_country?: string | null;
  net_weight_kg?: number | null;
}

export interface ProductTranslationRead {
  language: Language;
  name: string | null;
  description: string | null;
  status: TranslationStatus;
  updated_at: string;
  approved_at: string | null;
  approved_by: string | null;
}

export interface ProductImage {
  id: string;
  url: string;
  is_primary: boolean;
  alt: string | null;
  position: number;
  created_at: string;
}

export interface ProductListItem {
  internal_id: string;
  sku: string;
  name_en: string;
  family: string | null;
  subfamily: string | null;
  dn: string | null;
  pn: string | null;
  material: string | null;
  type: string | null;
  data_quality: DataQuality;
  translation_status_es: TranslationStatus | null;
  translation_status_ar: TranslationStatus | null;
  active: boolean;
  primary_image_url: string | null;
  updated_at: string;
  // Stage 3 (Wave 11) — taxonomy refinement
  series_id: string | null;
  material_id: string | null;
  display_pair_sku: string | null;
  division_codes: string[];
}

export interface ProductMini {
  sku: string;
  name_en: string;
  primary_image_url: string | null;
}

export interface Product extends ProductListItem {
  connection: string | null;
  weight_kg: number | null;
  dimensions: ProductDimensions | null;
  packaging: ProductPackaging | null;
  intrastat: ProductIntrastat | null;
  description_en: string | null;
  created_at: string;
}

export interface ProductListResponse {
  items: ProductListItem[];
  next_cursor: string | null;
  total: number | null;
  page_size: number;
}

export interface ProductCreatePayload {
  sku: string;
  name_en: string;
  family?: string | null;
  subfamily?: string | null;
  dn?: string | null;
  pn?: string | null;
  material?: string | null;
  type?: string | null;
  connection?: string | null;
  weight_kg?: number | null;
  dimensions?: ProductDimensions | null;
  packaging?: ProductPackaging | null;
  intrastat?: ProductIntrastat | null;
  description_en?: string | null;
  active?: boolean;
  /**
   * Stage 4 (Option C): structured `specs` JSONB validated by backend
   * SpecsValidator against the family/subfamily JSON Schema.
   */
  specs?: Record<string, unknown> | null;
  // Stage 3 (Wave 11) — taxonomy refinement at creation time.
  series_id?: string | null;
  material_id?: string | null;
  display_pair_sku?: string | null;
  division_codes?: string[];
}

export type ProductUpdatePayload = Partial<ProductCreatePayload>;

export interface ProductSearchHit {
  id: string;
  sku: string;
  name_en: string;
  family: string | null;
}

export interface UploadUrlResponse {
  storage_path: string;
  upload_url: string;
  token: string;
  method: "PUT";
  headers: Record<string, string>;
  expires_in: number;
  bucket: string;
}

export interface ImageConfirmPayload {
  storage_path: string;
  mime_type: string;
  bytes_size?: number;
  width?: number;
  height?: number;
  alt_text?: string;
  is_primary?: boolean;
  role?: string;
}

export interface ProductImageRecord {
  id: string;
  sku: string;
  role: string;
  storage_path: string;
  original_url: string | null;
  is_primary: boolean;
  alt_text: string | null;
  width: number | null;
  height: number | null;
  bytes_size: number | null;
  mime_type: string | null;
  status: string;
  created_at: string;
}

export interface TranslationUpsertPayload {
  name?: string | null;
  description?: string | null;
}

export interface ProductFilters {
  family?: string | undefined;
  data_quality?: DataQuality | undefined;
  translation_status?: TranslationStatus | undefined;
  active?: boolean | undefined;
  search?: string | undefined;
  /** US-1A-02-09: filtros avanzados consumidos por backend extendido en S2. */
  dn?: string | undefined;
  pn?: string | undefined;
  material?: string | undefined;
  created_after?: string | undefined;
  created_before?: string | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
  // Stage 3 (Wave 11) — taxonomy filters
  division?: string | undefined;
  series_id?: string | undefined;
  material_id?: string | undefined;
  tier_code?: string | undefined;
}

// ---- Internals ------------------------------------------------------------

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

export class ProductsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "ProductsApiError";
    this.status = status;
    this.detail = detail;
  }

  /** Devuelve un mapa fieldName → mensaje si el backend retornó un Pydantic error. */
  public fieldErrors(): Record<string, string> | null {
    const detail = this.detail;
    if (!detail || typeof detail !== "object") return null;
    const arr = (detail as { detail?: unknown }).detail;
    if (!Array.isArray(arr)) return null;
    const out: Record<string, string> = {};
    for (const it of arr) {
      if (!it || typeof it !== "object") continue;
      const loc = (it as { loc?: unknown }).loc;
      const msg = (it as { msg?: unknown }).msg;
      if (Array.isArray(loc) && typeof msg === "string") {
        const key = loc.filter((p) => p !== "body").join(".");
        if (key) out[key] = msg;
      }
    }
    return Object.keys(out).length > 0 ? out : null;
  }
}

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    search.set(k, String(v));
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

// ---- API ------------------------------------------------------------------

interface BackendPagination<T> {
  items: T[];
  cursor: { next: string | null; prev?: string | null };
  total: number | null;
  page_size: number;
}

export const productsApi = {
  list: async (filters: ProductFilters = {}): Promise<ProductListResponse> => {
    const raw = await authedFetch<BackendPagination<ProductListItem>>(
      `/api/v1/products${buildQuery({
        family: filters.family,
        data_quality: filters.data_quality,
        translation_status: filters.translation_status,
        active: filters.active,
        // US-1A-02-09 backend acepta `q`; mantenemos `search` como alias por
        // compatibilidad mientras el contrato consolida.
        q: filters.search,
        search: filters.search,
        dn: filters.dn,
        pn: filters.pn,
        material: filters.material,
        created_after: filters.created_after,
        created_before: filters.created_before,
        // Stage 3 — taxonomy filters
        division: filters.division,
        series_id: filters.series_id,
        material_id: filters.material_id,
        tier_code: filters.tier_code,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
      })}`,
    );
    return {
      items: raw.items,
      next_cursor: raw.cursor?.next ?? null,
      total: raw.total,
      page_size: raw.page_size,
    };
  },
  get: (id: string): Promise<Product> => authedFetch<Product>(`/api/v1/products/${id}`),
  create: (payload: ProductCreatePayload): Promise<Product> =>
    authedFetch<Product>("/api/v1/products", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  update: (id: string, payload: ProductUpdatePayload): Promise<Product> =>
    authedFetch<Product>(`/api/v1/products/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  remove: (id: string): Promise<void> =>
    authedFetch<void>(`/api/v1/products/${id}`, { method: "DELETE" }),
  search: (q: string, limit = 8): Promise<ProductSearchHit[]> =>
    authedFetch<ProductSearchHit[]>(
      `/api/v1/products/search${buildQuery({ q, limit })}`,
    ),
  // Translations
  listTranslations: (productId: string): Promise<ProductTranslationRead[]> =>
    authedFetch<ProductTranslationRead[]>(`/api/v1/products/${productId}/translations`),
  upsertTranslation: (
    productId: string,
    lang: Language,
    payload: TranslationUpsertPayload,
  ): Promise<ProductTranslationRead> =>
    authedFetch<ProductTranslationRead>(
      `/api/v1/products/${productId}/translations/${lang}`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    ),
  approveTranslation: (productId: string, lang: Language): Promise<ProductTranslationRead> =>
    authedFetch<ProductTranslationRead>(
      `/api/v1/products/${productId}/translations/${lang}/approve`,
      { method: "POST" },
    ),
  // Images
  listImages: (productId: string): Promise<ProductImage[]> =>
    authedFetch<ProductImage[]>(`/api/v1/products/${productId}/images`),
  getUploadUrl: (
    productId: string,
    fileName: string,
    contentType: string,
  ): Promise<UploadUrlResponse> =>
    // Backend espera `filename` + `content_type` (snake-case y nombre canónico
    // del schema Pydantic `ProductImageUploadRequest`).
    authedFetch<UploadUrlResponse>(`/api/v1/products/${productId}/images/upload-url`, {
      method: "POST",
      body: JSON.stringify({ filename: fileName, content_type: contentType }),
    }),
  confirmImageUpload: (
    productId: string,
    payload: ImageConfirmPayload,
  ): Promise<ProductImageRecord> =>
    authedFetch<ProductImageRecord>(`/api/v1/products/${productId}/images/confirm`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  setPrimaryImage: (productId: string, imageId: string): Promise<ProductImage> =>
    authedFetch<ProductImage>(
      `/api/v1/products/${productId}/images/${imageId}/set-primary`,
      { method: "POST" },
    ),
  deleteImage: (productId: string, imageId: string): Promise<void> =>
    authedFetch<void>(`/api/v1/products/${productId}/images/${imageId}`, {
      method: "DELETE",
    }),
};

export const PRODUCT_FAMILIES = [
  "valves",
  "fittings",
  "pipes",
  "flanges",
  "actuators",
  "accessories",
] as const;
export type ProductFamily = (typeof PRODUCT_FAMILIES)[number];
