"use client";

import { useInfiniteQuery } from "@tanstack/react-query";
import {
  productsApi,
  type ProductFilters,
  type ProductListResponse,
} from "@/lib/api/endpoints/products";
import { productKeys } from "./query-keys";

const DEFAULT_LIMIT = 25;

/**
 * Lista paginada cursor-based de productos.
 *
 * Devuelve `useInfiniteQuery` con `fetchNextPage` para paginación.
 * Filtros vivientes en el queryKey → cambio de filtros = nueva query.
 */
export function useProducts(filters: ProductFilters = {}) {
  return useInfiniteQuery<
    ProductListResponse,
    Error,
    { pages: ProductListResponse[]; pageParams: (string | null)[] },
    ReturnType<typeof productKeys.list>,
    string | null
  >({
    queryKey: productKeys.list(filters),
    queryFn: ({ pageParam }) =>
      productsApi.list({ ...filters, cursor: pageParam, limit: filters.limit ?? DEFAULT_LIMIT }),
    initialPageParam: null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    staleTime: 30_000,
  });
}
