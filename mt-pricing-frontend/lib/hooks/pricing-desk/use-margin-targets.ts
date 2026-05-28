"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  pricingDeskApi,
  type MarginTarget,
  type MarginTargetUpsert,
  type MarginOverrideRead,
  type MarginOverrideUpsert,
  type SellingModel,
} from "@/lib/api/endpoints/pricing-desk";

// ─── Query keys ──────────────────────────────────────────────────────────────

export const marginTargetKeys = {
  targets: (channelCode: string) =>
    ["pricing-desk", "margin-targets", channelCode] as const,
};

// ─── Queries ─────────────────────────────────────────────────────────────────

export function useMarginTargets(channelCode: string) {
  return useQuery<MarginTarget[], Error>({
    queryKey: marginTargetKeys.targets(channelCode),
    queryFn: () => pricingDeskApi.listMarginTargets(channelCode),
    enabled: !!channelCode,
    staleTime: 30_000,
  });
}

// ─── Mutations ───────────────────────────────────────────────────────────────

export function useUpsertMarginTarget(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (body: MarginTargetUpsert) =>
      pricingDeskApi.upsertMarginTarget(channelCode, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: marginTargetKeys.targets(channelCode),
      });
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}

export function useUpsertMarginOverride(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation<
    MarginOverrideRead,
    Error,
    { sku: string; body: MarginOverrideUpsert }
  >({
    mutationFn: ({ sku, body }) =>
      pricingDeskApi.upsertMarginOverride(channelCode, sku, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}

export function useDeleteMarginOverride(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation<void, Error, { sku: string; sellingModel: SellingModel }>({
    mutationFn: ({ sku, sellingModel }) =>
      pricingDeskApi.deleteMarginOverride(channelCode, sku, sellingModel),
    onSuccess: () => {
      void queryClient.invalidateQueries({
        queryKey: ["pricing-desk", "catalog", channelCode],
      });
    },
  });
}
