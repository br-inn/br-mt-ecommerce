"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  adminPimApi,
  type PimDataQualityReport,
} from "@/lib/api/endpoints/admin-pim";

const KEYS = {
  all: () => ["admin-pim"] as const,
  dataQuality: () => [...KEYS.all(), "data-quality"] as const,
};

/** Snapshot de calidad del catálogo PIM. */
export function usePimDataQuality() {
  const qc = useQueryClient();
  const query = useQuery<PimDataQualityReport, Error>({
    queryKey: KEYS.dataQuality(),
    queryFn: () => adminPimApi.getDataQuality(),
    staleTime: 60_000,
  });

  function invalidate() {
    void qc.invalidateQueries({ queryKey: KEYS.all() });
  }

  return { ...query, invalidate };
}

export const adminPimKeys = KEYS;
