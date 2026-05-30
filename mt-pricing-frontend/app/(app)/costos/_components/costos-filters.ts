"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useCallback, useMemo } from "react";

/**
 * Filtros del listado global `/costos` (tab "Costes") con estado en URL.
 *
 * Mapea 1:1 con `CostFilters` del cliente API:
 *   - `sku`            ↔ query `q` (o `sku`)
 *   - `scheme`         ↔ query `scheme`
 *   - `supplier`       ↔ query `supplier`
 *   - `valid_on`       ↔ query `valid_on` (fecha "YYYY-MM-DD")
 *   - `include_history`↔ query `include_history` ("true")
 */
export interface CostosListFilters {
  sku: string | undefined;
  scheme: string | undefined;
  supplier: string | undefined;
  valid_on: string | undefined;
  include_history: boolean | undefined;
}

export type CostosFilterKey =
  | "q"
  | "scheme"
  | "supplier"
  | "valid_on"
  | "include_history";

export function useCostosListFilters() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters: CostosListFilters = useMemo(() => {
    const historyRaw = sp.get("include_history");
    return {
      sku: sp.get("q") ?? sp.get("sku") ?? undefined,
      scheme: sp.get("scheme") ?? undefined,
      supplier: sp.get("supplier") ?? undefined,
      valid_on: sp.get("valid_on") ?? undefined,
      include_history: historyRaw === "true" ? true : undefined,
    };
  }, [sp]);

  const setFilter = useCallback(
    (key: CostosFilterKey, value: string | undefined) => {
      const params = new URLSearchParams(Array.from(sp.entries()));
      // `sku` y `q` son alias: nunca dejar ambos.
      if (key === "q") params.delete("sku");
      if (value && value.length > 0) {
        params.set(key, value);
      } else {
        params.delete(key);
      }
      const qs = params.toString();
      router.replace(qs.length > 0 ? `${pathname}?${qs}` : pathname);
    },
    [sp, router, pathname],
  );

  const clear = useCallback(() => {
    router.replace(pathname);
  }, [router, pathname]);

  const hasFilters = Boolean(
    filters.sku ||
      filters.scheme ||
      filters.supplier ||
      filters.valid_on ||
      filters.include_history,
  );

  return { filters, setFilter, clear, hasFilters };
}
