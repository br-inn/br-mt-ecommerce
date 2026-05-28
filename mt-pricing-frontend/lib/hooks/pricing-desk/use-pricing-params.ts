"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  pricingDeskApi,
  type PricingParamsResponse,
  type TradeRouteParamsUpdate,
  type ChannelFeeParamsUpdate,
} from "@/lib/api/endpoints/pricing-desk";

// ─── Query keys ──────────────────────────────────────────────────────────────

export const pricingParamsKeys = {
  params: (channelCode: string) =>
    ["pricing-desk", "params", channelCode] as const,
};

// ─── Queries ─────────────────────────────────────────────────────────────────

export function usePricingParams(channelCode: string) {
  return useQuery<PricingParamsResponse, Error>({
    queryKey: pricingParamsKeys.params(channelCode),
    queryFn: () => pricingDeskApi.getParams(channelCode),
    enabled: !!channelCode,
    staleTime: 30_000,
  });
}

// ─── Mutations ───────────────────────────────────────────────────────────────

export function useUpdateRouteParams(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<TradeRouteParamsUpdate>) =>
      pricingDeskApi.updateRouteParams(channelCode, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: pricingParamsKeys.params(channelCode),
      });
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}

export function useUpdateFeeParams(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: Partial<ChannelFeeParamsUpdate>) =>
      pricingDeskApi.updateFeeParams(channelCode, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: pricingParamsKeys.params(channelCode),
      });
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}
