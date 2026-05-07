"use client";

import { useQuery } from "@tanstack/react-query";

import {
  dashboardApi,
  type DashboardStats,
} from "@/lib/api/endpoints/dashboard";

/**
 * Hook TanStack Query para los KPIs del dashboard.
 *
 * - `refetchInterval: 30_000` — refresca cada 30s en background.
 * - `staleTime: 15_000` — evita refetches duplicados durante el render.
 * - Cancela automáticamente al desmontar el componente.
 */
export function useDashboardStats() {
  return useQuery<DashboardStats, Error>({
    queryKey: ["dashboard", "stats"],
    queryFn: dashboardApi.getStats,
    refetchInterval: 30_000,
    staleTime: 15_000,
  });
}
