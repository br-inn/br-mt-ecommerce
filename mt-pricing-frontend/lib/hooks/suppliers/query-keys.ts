import type { SupplierFilters } from "@/lib/api/endpoints/suppliers";

/**
 * Query keys centralizados para suppliers (TanStack Query) — patrón espejo a `productKeys`.
 */
export const supplierKeys = {
  all: () => ["suppliers"] as const,
  lists: () => [...supplierKeys.all(), "list"] as const,
  list: (filters: SupplierFilters) => [...supplierKeys.lists(), filters] as const,
  details: () => [...supplierKeys.all(), "detail"] as const,
  detail: (id: string) => [...supplierKeys.details(), id] as const,
};
