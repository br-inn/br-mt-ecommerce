"use client";

import { useQuery } from "@tanstack/react-query";
import { productsApi, type BoreDimension } from "@/lib/api/endpoints/products";
import { productKeys } from "./query-keys";

export function useProductBoreDimensions(sku: string | undefined) {
  return useQuery<BoreDimension[], Error>({
    queryKey: productKeys.boreDimensions(sku ?? ""),
    queryFn: () => productsApi.listBoreDimensions(sku as string),
    enabled: !!sku,
    staleTime: 60_000,
  });
}
