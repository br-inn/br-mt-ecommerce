"use client";

import { useQuery } from "@tanstack/react-query";
import { facetsApi, type FacetsFilters, type FacetsResponse } from "@/lib/api/endpoints/facets";
import { useDebouncedValue } from "@/lib/hooks/use-debounced-value";

export type { FacetsFilters, FacetsResponse } from "@/lib/api/endpoints/facets";

const DEFAULT_STALE_MS = 30_000;
const FACET_DEBOUNCE_MS = 400;

export function useFacets(filters: FacetsFilters = {}) {
  const debouncedFilters = useDebouncedValue(filters, FACET_DEBOUNCE_MS);
  return useQuery<FacetsResponse>({
    queryKey: ["products", "facets", debouncedFilters],
    queryFn: () => facetsApi.get(debouncedFilters),
    staleTime: DEFAULT_STALE_MS,
    gcTime: 5 * 60_000,
  });
}
