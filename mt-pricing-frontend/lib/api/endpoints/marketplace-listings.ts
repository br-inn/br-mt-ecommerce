"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

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
// Auth-aware fetch helper (same pattern as matches.ts)
// ---------------------------------------------------------------------------

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
    const msg =
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
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
