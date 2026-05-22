"use client";

import { authedFetch } from "@/lib/api/client";

/**
 * API client for PIM translation completion + coverage endpoints.
 * Backend: POST /api/v1/products/translations/complete
 *          GET  /api/v1/products/translations/coverage
 */

// ---- Types ------------------------------------------------------------------

export interface CompleteTranslationsRequest {
  skus: string[];
  target_langs: string[];
  source_lang?: string;
}

export interface CompletionDetail {
  sku: string;
  lang: string;
  status: string;
}

export interface CompletionResult {
  completed: number;
  skipped: number;
  errors: number;
  details: CompletionDetail[];
}

export interface CoverageEntry {
  lang: string;
  count: number;
  pct: number;
}

export interface TranslationCoverage {
  total_products: number;
  coverage: CoverageEntry[];
  missing_by_lang: Record<string, number>;
}

// ---- API calls --------------------------------------------------------------

export const translationsApi = {
  complete: (payload: CompleteTranslationsRequest): Promise<CompletionResult> =>
    authedFetch<CompletionResult>("/api/v1/products/translations/complete", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  coverage: (): Promise<TranslationCoverage> =>
    authedFetch<TranslationCoverage>("/api/v1/products/translations/coverage"),
};
