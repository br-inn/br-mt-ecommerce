"use client";

import { useQuery } from "@tanstack/react-query";

import { facetsApi, type FacetsFilters, type FacetsResponse } from "@/lib/api/endpoints/facets";

const DEFAULT_STALE_MS = 30_000;

export function useFacets(filters: FacetsFilters = {}) {
  return useQuery<FacetsResponse>({
    queryKey: ["products", "facets", filters],
    queryFn: () => facetsApi.get(filters),
    staleTime: DEFAULT_STALE_MS,
    gcTime: 5 * 60_000,
  });
}
