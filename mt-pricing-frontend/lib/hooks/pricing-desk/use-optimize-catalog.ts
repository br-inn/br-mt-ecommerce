"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  pricingDeskApi,
  type OptimizeResponse,
  type SellingModel,
} from "@/lib/api/endpoints/pricing-desk";

// ─── Mutations ───────────────────────────────────────────────────────────────

export function useOptimizeCatalog(channelCode: string) {
  return useMutation<OptimizeResponse, Error, SellingModel>({
    mutationFn: (sellingModel: SellingModel) =>
      pricingDeskApi.optimizeCatalog(channelCode, sellingModel),
  });
}

export function useApplyOptimization(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, SellingModel>({
    mutationFn: (sellingModel: SellingModel) =>
      pricingDeskApi.applyOptimization(channelCode, sellingModel),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}
