import { useMutation, useQueryClient } from "@tanstack/react-query";
import { productsApi } from "@/lib/api/endpoints/products";
import type { DataQuality } from "@/lib/api/endpoints/products";
import { productKeys } from "@/lib/hooks/products/query-keys";

export interface PatchDataQualityPayload {
  new_value: DataQuality;
  reason?: string;
}

export function usePatchDataQuality(sku: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (payload: PatchDataQualityPayload) =>
      productsApi.patchDataQuality(sku, payload),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: productKeys.detail(sku) });
    },
  });
}
