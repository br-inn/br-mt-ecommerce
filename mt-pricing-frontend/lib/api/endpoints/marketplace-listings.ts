"use client";

import env from "@/lib/env";
import { authedFetch } from "@/lib/api/client";

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
   * Returns the URL for the CSV export endpoint.
   * Open with window.open() to trigger a browser download.
   */
  getExportUrl: (): string =>
    `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/marketplace-listings/amazon_uae/export`,
};
