"use client";

import { useQuery } from "@tanstack/react-query";
import { productsApi, type Product } from "@/lib/api/endpoints/products";
import { productKeys } from "./query-keys";

/**
 * Detalle de un producto por id (UUID) o por SKU.
 * El backend acepta ambos en `GET /products/{id}`.
 */
export function useProduct(idOrSku: string | undefined, enabled = true) {
  return useQuery<Product, Error>({
    queryKey: productKeys.detail(idOrSku ?? ""),
    queryFn: () => productsApi.get(idOrSku as string),
    enabled: enabled && !!idOrSku,
    staleTime: 60_000,
  });
}
