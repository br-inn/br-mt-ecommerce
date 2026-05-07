import type { ProductFilters } from "@/lib/api/endpoints/products";

/**
 * Centraliza los queryKey de TanStack Query para productos.
 * Usar SIEMPRE estas constantes para invalidación coherente.
 */
export const productKeys = {
  all: () => ["products"] as const,
  lists: () => [...productKeys.all(), "list"] as const,
  list: (filters: ProductFilters) => [...productKeys.lists(), filters] as const,
  details: () => [...productKeys.all(), "detail"] as const,
  detail: (id: string) => [...productKeys.details(), id] as const,
  translations: (id: string) => [...productKeys.detail(id), "translations"] as const,
  images: (id: string) => [...productKeys.detail(id), "images"] as const,
  search: (q: string) => [...productKeys.all(), "search", q] as const,
};
