"use client";

import { useQuery } from "@tanstack/react-query";

import {
  costDashboardApi,
  type CostDashboardOverview,
} from "@/lib/api/endpoints/cost-dashboard";

const KEYS = {
  all: () => ["cost-dashboard"] as const,
  overview: (totalProducts: number) =>
    [...KEYS.all(), "overview", { totalProducts }] as const,
};

/**
 * Cost dashboard overview — N requests paralelos a `/costs/missing` por scheme.
 * Acepta `totalProducts` (viene del KPI de productos) para calcular cobertura.
 */
export function useCostDashboardOverview(totalProducts: number, enabled = true) {
  return useQuery<CostDashboardOverview, Error>({
    queryKey: KEYS.overview(totalProducts),
    queryFn: () => costDashboardApi.overview(totalProducts),
    enabled: enabled && totalProducts > 0,
    staleTime: 60_000,
  });
}

export const costDashboardKeys = KEYS;
