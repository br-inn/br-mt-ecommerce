"use client";

import { useQuery, keepPreviousData } from "@tanstack/react-query";
import {
  productsApi,
  type ProductFilters,
  type ProductListResponse,
} from "@/lib/api/endpoints/products";
import { productKeys } from "./query-keys";

/**
 * Lista paginada de productos con offset pagination.
 *
 * Pasa `page` dentro de `filters` para activar offset mode en el backend.
 * Usa `keepPreviousData` para evitar parpadeo al cambiar de página.
 */
export function useProducts(filters: ProductFilters = {}) {
  return useQuery<ProductListResponse>({
    queryKey: productKeys.list(filters),
    queryFn: () => productsApi.list(filters),
    staleTime: 30_000,
    placeholderData: keepPreviousData,
  });
}
