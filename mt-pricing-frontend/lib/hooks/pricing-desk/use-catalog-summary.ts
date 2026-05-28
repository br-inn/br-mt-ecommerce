"use client";

import { useQuery } from "@tanstack/react-query";
import {
  pricingDeskApi,
  type CatalogSummary,
  type SellingModel,
} from "@/lib/api/endpoints/pricing-desk";

// ─── Types ───────────────────────────────────────────────────────────────────

export interface CatalogFilters {
  familyId?: string;
  signal?: string;
}

// ─── Query keys ──────────────────────────────────────────────────────────────

export const catalogSummaryKeys = {
  catalog: (
    channelCode: string,
    sellingModel: SellingModel,
    filters: CatalogFilters,
  ) =>
    [
      "pricing-desk",
      "catalog",
      channelCode,
      sellingModel,
      filters,
    ] as const,
};

// ─── Queries ─────────────────────────────────────────────────────────────────

export function useCatalogSummary(
  channelCode: string,
  sellingModel: SellingModel,
  filters: CatalogFilters,
) {
  return useQuery<CatalogSummary, Error>({
    queryKey: catalogSummaryKeys.catalog(channelCode, sellingModel, filters),
    queryFn: () => {
      const opts: {
        sellingModel?: SellingModel;
        familyId?: string;
        signal?: string;
      } = { sellingModel };
      if (filters.familyId !== undefined) opts.familyId = filters.familyId;
      if (filters.signal !== undefined) opts.signal = filters.signal;
      return pricingDeskApi.getCatalogSummary(channelCode, opts);
    },
    enabled: !!channelCode,
    staleTime: 30_000,
  });
}
