"use client";

import { useQuery } from "@tanstack/react-query";
import { pricingDeskApi, type SellingModel } from "@/lib/api/endpoints/pricing-desk";

export function useProductPrice(
  channelCode: string,
  sku: string | null,
  sellingModel: SellingModel,
) {
  return useQuery({
    queryKey: ["pricing-desk", "product-price", channelCode, sku, sellingModel],
    queryFn: () => pricingDeskApi.getProductPrice(channelCode, sku!, sellingModel),
    enabled: !!sku,
    staleTime: 30_000,
  });
}
