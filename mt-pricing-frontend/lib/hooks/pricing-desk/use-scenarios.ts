"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";

export function useScenarios(channelCode: string, sellingModel: SellingModel) {
  return useQuery({
    queryKey: ["pricing-desk", "scenarios", channelCode, sellingModel],
    queryFn: () => pricingDeskApi.listScenarios(channelCode, sellingModel),
    enabled: !!channelCode,
  });
}

export function useSaveScenario(channelCode: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({
      slot,
      sellingModel,
      label,
    }: {
      slot: "A" | "B";
      sellingModel: SellingModel;
      label?: string;
    }) =>
      pricingDeskApi.saveScenario(channelCode, slot, {
        selling_model: sellingModel,
        slot,
        ...(label && { label }),
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pricing-desk", "scenarios", channelCode] });
    },
  });
}

export function useLoadScenario(channelCode: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ slot, sellingModel }: { slot: "A" | "B"; sellingModel: SellingModel }) =>
      pricingDeskApi.loadScenario(channelCode, slot, sellingModel),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["pricing-desk", "params", channelCode] });
      qc.invalidateQueries({ queryKey: ["pricing-desk", "margin-targets", channelCode] });
      qc.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
    },
  });
}
