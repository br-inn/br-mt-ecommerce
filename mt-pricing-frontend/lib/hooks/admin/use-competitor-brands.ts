"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  competitorBrandsApi,
  type BrandScrapeRunRequest,
  type BrandScrapeRunResponse,
  type CompetitorBrandCreate,
  type CompetitorBrandRead,
  type CompetitorBrandUpdate,
  type MonitoringToggleResponse,
} from "@/lib/api/endpoints/competitor-brands";

const KEYS = {
  all: () => ["competitor-brands"] as const,
  list: (active_only: boolean) => [...KEYS.all(), "list", active_only] as const,
};

export function useCompetitorBrands(active_only = false) {
  return useQuery<CompetitorBrandRead[], Error>({
    queryKey: KEYS.list(active_only),
    queryFn: () => competitorBrandsApi.list(active_only),
    staleTime: 30_000,
  });
}

export function useCreateCompetitorBrand() {
  const qc = useQueryClient();
  return useMutation<CompetitorBrandRead, Error, CompetitorBrandCreate>({
    mutationFn: (req) => competitorBrandsApi.create(req),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export function useUpdateCompetitorBrand() {
  const qc = useQueryClient();
  return useMutation<
    CompetitorBrandRead,
    Error,
    { id: string; data: CompetitorBrandUpdate }
  >({
    mutationFn: ({ id, data }) => competitorBrandsApi.update(id, data),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export function useRunBrandScrape() {
  return useMutation<BrandScrapeRunResponse, Error, BrandScrapeRunRequest>({
    mutationFn: (req) => competitorBrandsApi.run(req),
  });
}

/** US-SCR-04-03: toggle monitoreo continuo */
export function useToggleCompetitorBrandMonitoring() {
  const qc = useQueryClient();
  return useMutation<MonitoringToggleResponse, Error, string>({
    mutationFn: (id) => competitorBrandsApi.toggleMonitoring(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: KEYS.all() }),
  });
}

export const competitorBrandKeys = KEYS;
