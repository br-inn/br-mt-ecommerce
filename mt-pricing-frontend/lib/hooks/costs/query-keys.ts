import type { CostFilters } from "@/lib/api/endpoints/costs";

/** Query keys centralizados para costs (TanStack Query). */
export const costKeys = {
  all: () => ["costs"] as const,
  lists: () => [...costKeys.all(), "list"] as const,
  list: (filters: CostFilters) => [...costKeys.lists(), filters] as const,
  details: () => [...costKeys.all(), "detail"] as const,
  detail: (id: string) => [...costKeys.details(), id] as const,
};
