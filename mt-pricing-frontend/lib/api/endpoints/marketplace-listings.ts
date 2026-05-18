"use client";

import { authedFetch, authedDownload } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AmazonFieldError {
  field: string;
  code: string;
  message: string;
}

export interface AmazonListingValidation {
  sku: string;
  is_ready: boolean;
  errors: AmazonFieldError[];
  warnings: AmazonFieldError[];
}

export interface AmazonValidationReport {
  total_skus: number;
  ready_count: number;
  draft_count: number;
  error_count: number;
  listings: AmazonListingValidation[];
}

export interface MarketplaceListingRead {
  id: string;
  product_sku: string;
  marketplace: string;
  status: "draft" | "ready" | "published" | "paused";
  listing_title: string | null;
  listing_description: string | null;
  bullet_points: string[];
  search_keywords: string | null;
  extra: Record<string, unknown>;
  ai_generated_at: string | null;
  ai_model: string | null;
  created_at: string;
  updated_at: string;
}

export interface MarketplaceListingUpsert {
  status?: "draft" | "ready" | "published" | "paused";
  listing_title?: string | null;
  listing_description?: string | null;
  bullet_points?: string[];
  search_keywords?: string | null;
  extra?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// API surface
// ---------------------------------------------------------------------------

export const marketplaceListingsApi = {
  /**
   * GET /api/v1/marketplace-listings/amazon_uae/validate
   * Returns a validation report for all products.
   */
  validateAmazon: (): Promise<AmazonValidationReport> =>
    authedFetch<AmazonValidationReport>("/api/v1/marketplace-listings/amazon_uae/validate"),

  /**
   * POST /api/v1/marketplace-listings/{sku}/amazon_uae/generate
   * Triggers AI generation for a single SKU.
   */
  generateListing: (sku: string, overwrite = false): Promise<MarketplaceListingRead> =>
    authedFetch<MarketplaceListingRead>(
      `/api/v1/marketplace-listings/${encodeURIComponent(sku)}/amazon_uae/generate`,
      {
        method: "POST",
        body: JSON.stringify({ overwrite }),
      },
    ),

  /**
   * GET /api/v1/marketplace-listings/{sku}/amazon_uae
   * Returns the full listing content for a single SKU.
   */
  getListing: (sku: string): Promise<MarketplaceListingRead> =>
    authedFetch<MarketplaceListingRead>(
      `/api/v1/marketplace-listings/${encodeURIComponent(sku)}/amazon_uae`,
    ),

  /**
   * PUT /api/v1/marketplace-listings/{sku}/amazon_uae
   * Creates or updates a listing (manual edits, not AI).
   */
  upsertListing: (sku: string, body: MarketplaceListingUpsert): Promise<MarketplaceListingRead> =>
    authedFetch<MarketplaceListingRead>(
      `/api/v1/marketplace-listings/${encodeURIComponent(sku)}/amazon_uae`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    ),

  /**
   * Returns validation for a specific SKU by fetching the full report and filtering.
   */
  validateSku: (sku: string): Promise<AmazonListingValidation> =>
    authedFetch<AmazonValidationReport>(`/api/v1/marketplace-listings/amazon_uae/validate`).then(
      (report) => {
        const found = report.listings.find((l) => l.sku === sku);
        if (!found) throw new Error(`SKU ${sku} not found in validation report`);
        return found;
      },
    ),

  /**
   * Descarga el CSV de Amazon UAE con autenticación Bearer.
   * Pasa `skus` para restringir la exportación a un subconjunto.
   */
  downloadExport: (skus?: string[]): Promise<void> => {
    const params = new URLSearchParams();
    if (skus && skus.length > 0) params.set("skus", skus.join(","));
    const qs = params.toString();
    const path = `/api/v1/marketplace-listings/amazon_uae/export${qs ? `?${qs}` : ""}`;
    const date = new Date().toISOString().slice(0, 10).replace(/-/g, "");
    const filename = skus?.length ? `AMAZON_UAE_SELECCION_${date}.csv` : `AMAZON_UAE_${date}.csv`;
    return authedDownload(path, filename);
  },
};
