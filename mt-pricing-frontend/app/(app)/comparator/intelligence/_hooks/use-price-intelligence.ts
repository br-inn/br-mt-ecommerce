"use client";

import useSWR from "swr";
import {
  fetchPriceIntelligenceDashboard,
  fetchPriceIntelligenceQuality,
  fetchBrandListings,
  type DashboardResponse,
  type QualityResponse,
  type ListingsResponse,
} from "@/lib/api/endpoints/price-intelligence";

// ── Dashboard ──────────────────────────────────────────────────────────────────

export interface UsePriceIntelligenceDashboardParams {
  brandId?: string;
  marketplace?: string;
  dateFrom?: string;
  dateTo?: string;
}

export function usePriceIntelligenceDashboard(params: UsePriceIntelligenceDashboardParams = {}) {
  const key = [
    "price-intelligence-dashboard",
    params.brandId ?? "",
    params.marketplace ?? "",
    params.dateFrom ?? "",
    params.dateTo ?? "",
  ];

  return useSWR<DashboardResponse>(
    key,
    () =>
      fetchPriceIntelligenceDashboard({
        brandId: params.brandId,
        marketplace: params.marketplace,
        dateFrom: params.dateFrom,
        dateTo: params.dateTo,
      }),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30_000,
    }
  );
}

// ── Quality ────────────────────────────────────────────────────────────────────

export function usePriceIntelligenceQuality() {
  return useSWR<QualityResponse>(
    "price-intelligence-quality",
    () => fetchPriceIntelligenceQuality(),
    {
      revalidateOnFocus: false,
      dedupingInterval: 60_000,
    }
  );
}

// ── Brand listings ─────────────────────────────────────────────────────────────

export function useBrandListings(
  brandId: string | undefined,
  params?: { marketplace?: string; limit?: number; offset?: number }
) {
  return useSWR<ListingsResponse>(
    brandId ? ["price-intelligence-listings", brandId, params?.marketplace ?? "", params?.offset ?? 0] : null,
    () => fetchBrandListings(brandId!, params),
    {
      revalidateOnFocus: false,
      dedupingInterval: 30_000,
    }
  );
}
