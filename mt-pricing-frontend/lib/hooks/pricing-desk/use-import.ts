"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { pricingDeskApi } from "@/lib/api/endpoints/pricing-desk";

export function useImportCatalog(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, confirm }: { file: File; confirm: boolean }) =>
      pricingDeskApi.importCatalog(channelCode, file, confirm),
    onSuccess: (_data, { confirm }) => {
      if (confirm) {
        queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
      }
    },
  });
}

export function useImportLogistics(channelCode: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ file, confirm }: { file: File; confirm: boolean }) =>
      pricingDeskApi.importLogistics(channelCode, file, confirm),
    onSuccess: (_data, { confirm }) => {
      if (confirm) {
        queryClient.invalidateQueries({ queryKey: ["pricing-desk", "catalog", channelCode] });
      }
    },
  });
}
