"use client";

import { useInfiniteQuery, useQuery } from "@tanstack/react-query";
import {
  unmatchedOffersApi,
  type UnmatchedOffersFilters,
  type UnmatchedOffersListResponse,
} from "@/lib/api/endpoints/unmatched-offers";

const DEFAULT_LIMIT = 30;

// ---- Query keys -------------------------------------------------------------

export const unmatchedOffersKeys = {
  all: () => ["unmatched-offers"] as const,
  lists: () => [...unmatchedOffersKeys.all(), "list"] as const,
  list: (filters: UnmatchedOffersFilters) =>
    [...unmatchedOffersKeys.lists(), filters] as const,
  stats: () => [...unmatchedOffersKeys.all(), "stats"] as const,
};

// ---- useUnmatchedOffers -----------------------------------------------------

/**
 * Cursor-based infinite list of unmatched marketplace offers.
 * Mirrors the same pattern as `useProducts`.
 */
export function useUnmatchedOffers(filters: UnmatchedOffersFilters = {}) {
  return useInfiniteQuery<
    UnmatchedOffersListResponse,
    Error,
    { pages: UnmatchedOffersListResponse[]; pageParams: (string | null)[] },
    ReturnType<typeof unmatchedOffersKeys.list>,
    string | null
  >({
    queryKey: unmatchedOffersKeys.list(filters),
    queryFn: ({ pageParam }) =>
      unmatchedOffersApi.list({
        ...filters,
        cursor: pageParam,
        limit: filters.limit ?? DEFAULT_LIMIT,
      }),
    initialPageParam: null,
    getNextPageParam: (last) => last.next_cursor ?? undefined,
    staleTime: 30_000,
  });
}

// ---- useUnmatchedOffersStats ------------------------------------------------

export function useUnmatchedOffersStats() {
  return useQuery({
    queryKey: unmatchedOffersKeys.stats(),
    queryFn: () => unmatchedOffersApi.stats(),
    staleTime: 60_000,
  });
}
