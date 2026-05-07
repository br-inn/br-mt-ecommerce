"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import {
  translationsWorkflowApi,
  type MarkStalePayload,
  type MarkStaleResponse,
  type RejectPayload,
  type TranslationWorkflowRow,
} from "@/lib/api/endpoints/translations-workflow";
import type { Language } from "@/lib/api/endpoints/products";

import { productKeys } from "./query-keys";

/**
 * Hooks del Translations Approval Workflow (US-1A-02-05).
 *
 * NOTA: el endpoint clásico `approveTranslation` (POST /approve) sigue siendo
 * consumido por `useApproveTranslation` en `use-translations.ts`. Estos hooks
 * añaden las nuevas transiciones (`request-review`, `reject`, `mark-stale`).
 */

export function useRequestReviewTranslation(productId: string) {
  const qc = useQueryClient();
  return useMutation<TranslationWorkflowRow, Error, Language>({
    mutationFn: (lang) => translationsWorkflowApi.requestReview(productId, lang),
    onSuccess: (row) => {
      qc.setQueryData<TranslationWorkflowRow[]>(
        productKeys.translations(productId),
        (prev) => mergeRow(prev, row),
      );
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });
}

export function useRejectTranslation(productId: string) {
  const qc = useQueryClient();
  return useMutation<
    TranslationWorkflowRow,
    Error,
    { lang: Language; payload: RejectPayload }
  >({
    mutationFn: ({ lang, payload }) =>
      translationsWorkflowApi.reject(productId, lang, payload),
    onSuccess: (row) => {
      qc.setQueryData<TranslationWorkflowRow[]>(
        productKeys.translations(productId),
        (prev) => mergeRow(prev, row),
      );
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });
}

export function useMarkTranslationsStale(productId: string) {
  const qc = useQueryClient();
  return useMutation<MarkStaleResponse, Error, MarkStalePayload | undefined>({
    mutationFn: (payload) =>
      translationsWorkflowApi.markStale(productId, payload ?? {}),
    onSuccess: (resp) => {
      qc.setQueryData<TranslationWorkflowRow[]>(
        productKeys.translations(productId),
        (prev) => {
          if (!prev) return resp.affected;
          let next = prev;
          for (const r of resp.affected) {
            next = mergeRow(next, r) ?? next;
          }
          return next;
        },
      );
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });
}

function mergeRow(
  prev: TranslationWorkflowRow[] | undefined,
  row: TranslationWorkflowRow,
): TranslationWorkflowRow[] {
  if (!prev) return [row];
  const idx = prev.findIndex((r) => r.lang === row.lang);
  if (idx === -1) return [...prev, row];
  const out = [...prev];
  out[idx] = row;
  return out;
}
