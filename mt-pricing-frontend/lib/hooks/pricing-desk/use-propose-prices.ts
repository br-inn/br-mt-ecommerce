"use client";

import { useMutation } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";

export function useProposeSelected(channelCode: string) {
  return useMutation({
    mutationFn: ({
      skus,
      sellingModel,
      notes,
    }: {
      skus: string[];
      sellingModel: SellingModel;
      notes?: string;
    }) =>
      pricingDeskApi.proposeSelected(channelCode, {
        skus,
        selling_model: sellingModel,
        ...(notes && { notes }),
      }),
  });
}
