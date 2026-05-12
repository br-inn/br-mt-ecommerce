"use client";

import { useQuery } from "@tanstack/react-query";
import { sparePartsApi } from "@/lib/api/endpoints/spare-parts";
import type { ProductCompatibility } from "@/lib/api/endpoints/products";

/**
 * Hook que envuelve `GET /api/v1/series/{series_id}/spare-parts?dn={dn}`.
 *
 * Devuelve recambios (compatibility con owner_type='series') aplicables a la
 * serie. `dn` opcional restringe al rango `[dn_min, dn_max]` que lo contenga.
 */
export function useSparePartsForSeries(
  seriesId: string | undefined,
  dn?: number,
  enabled = true,
) {
  return useQuery<ProductCompatibility[], Error>({
    queryKey: ["series", seriesId, "spare-parts", { dn: dn ?? null }],
    queryFn: () => sparePartsApi.listSparePartsForSeries(seriesId as string, dn),
    enabled: enabled && !!seriesId,
    staleTime: 30_000,
  });
}
