"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  translationsApi,
  type CompleteTranslationsRequest,
  type CompletionResult,
  type TranslationCoverage,
} from "@/lib/api/endpoints/translations";

// ---- Query keys -------------------------------------------------------------

export const translationCoverageKeys = {
  all: () => ["translation-coverage"] as const,
};

// ---- Hooks ------------------------------------------------------------------

/**
 * Fetches per-language translation coverage across the full product catalog.
 * staleTime: 60_000 — product-level data per CLAUDE.md guidelines.
 */
export function useTranslationCoverage() {
  return useQuery<TranslationCoverage, Error>({
    queryKey: translationCoverageKeys.all(),
    queryFn: () => translationsApi.coverage(),
    staleTime: 60_000,
  });
}

/**
 * Triggers AI completion for the given SKU(s) + languages.
 * Invalidates coverage cache on success so the UI refreshes automatically.
 */
export function useCompleteTranslations() {
  const qc = useQueryClient();
  return useMutation<CompletionResult, Error, CompleteTranslationsRequest>({
    mutationFn: (payload) => translationsApi.complete(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: translationCoverageKeys.all() });
    },
  });
}
