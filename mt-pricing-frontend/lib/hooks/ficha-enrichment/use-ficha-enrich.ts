"use client";

import { useMutation } from "@tanstack/react-query";

import {
  applyFichaEnrich,
  applyFichaSeries,
  previewFichaEnrich,
  previewFichaSeries,
  type FichaEnrichApplyRequest,
  type FichaEnrichApplyResponse,
  type FichaEnrichPreviewResponse,
  type FichaSeriesApplyRequest,
  type FichaSeriesApplyResponse,
  type FichaSeriesPreviewResponse,
} from "@/lib/api/endpoints/ficha-enrich";

export function usePreviewFichaEnrich(sku: string) {
  return useMutation<FichaEnrichPreviewResponse, Error, File>({
    mutationFn: (file) => previewFichaEnrich(sku, file),
  });
}

export function useApplyFichaEnrich(sku: string) {
  return useMutation<FichaEnrichApplyResponse, Error, FichaEnrichApplyRequest>({
    mutationFn: (body) => applyFichaEnrich(sku, body),
  });
}

export function usePreviewFichaSeries() {
  return useMutation<FichaSeriesPreviewResponse, Error, File>({
    mutationFn: (file) => previewFichaSeries(file),
  });
}

export function useApplyFichaSeries() {
  return useMutation<FichaSeriesApplyResponse, Error, FichaSeriesApplyRequest>({
    mutationFn: (body) => applyFichaSeries(body),
  });
}
