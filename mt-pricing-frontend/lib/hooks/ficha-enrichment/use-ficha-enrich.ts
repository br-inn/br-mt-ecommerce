"use client";

import { useMutation } from "@tanstack/react-query";

import {
  applyFichaEnrich,
  previewFichaEnrich,
  type FichaEnrichApplyRequest,
  type FichaEnrichApplyResponse,
  type FichaEnrichPreviewResponse,
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
