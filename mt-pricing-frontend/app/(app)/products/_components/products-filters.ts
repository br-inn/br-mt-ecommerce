"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useCallback, useMemo } from "react";

import type { DataQuality } from "@/lib/api/endpoints/products";

/**
 * Filtros de la lista `/products` con state-in-URL (Pantalla 2).
 *
 * S1: family, brand, q.
 * S2 (US-1A-02-09 frontend): añade dn, pn, material, data_quality, active,
 * created_after, created_before. Search input usa debounce 300ms en el toolbar.
 */
export interface ProductsListFilters {
  family: string | undefined;
  brand: string | undefined;
  search: string | undefined;
  dn: string | undefined;
  pn: string | undefined;
  material: string | undefined;
  data_quality: DataQuality | undefined;
  active: boolean | undefined;
  created_after: string | undefined;
  created_before: string | undefined;
}

export type ProductsFilterKey =
  | "q"
  | "family"
  | "brand"
  | "dn"
  | "pn"
  | "material"
  | "data_quality"
  | "active"
  | "created_after"
  | "created_before";

const DATA_QUALITY_VALUES: ReadonlySet<string> = new Set([
  "complete",
  "partial",
  "blocked",
]);

export function useProductsListFilters() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters: ProductsListFilters = useMemo(() => {
    const dq = sp.get("data_quality") ?? undefined;
    const data_quality =
      dq && DATA_QUALITY_VALUES.has(dq) ? (dq as DataQuality) : undefined;
    const activeRaw = sp.get("active");
    const active =
      activeRaw === "true" ? true : activeRaw === "false" ? false : undefined;
    return {
      family: sp.get("family") ?? undefined,
      brand: sp.get("brand") ?? undefined,
      search: sp.get("q") ?? undefined,
      dn: sp.get("dn") ?? undefined,
      pn: sp.get("pn") ?? undefined,
      material: sp.get("material") ?? undefined,
      data_quality,
      active,
      created_after: sp.get("created_after") ?? undefined,
      created_before: sp.get("created_before") ?? undefined,
    };
  }, [sp]);

  const setFilter = useCallback(
    (key: ProductsFilterKey, value: string | undefined) => {
      const params = new URLSearchParams(Array.from(sp.entries()));
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
    filters.family ||
      filters.brand ||
      filters.search ||
      filters.dn ||
      filters.pn ||
      filters.material ||
      filters.data_quality ||
      filters.active !== undefined ||
      filters.created_after ||
      filters.created_before,
  );

  /** Cuántos filtros activos (para el badge del botón Más filtros). */
  const activeCount =
    Number(Boolean(filters.dn)) +
    Number(Boolean(filters.pn)) +
    Number(Boolean(filters.material)) +
    Number(Boolean(filters.data_quality)) +
    Number(filters.active !== undefined) +
    Number(Boolean(filters.created_after)) +
    Number(Boolean(filters.created_before));

  return { filters, setFilter, clear, hasFilters, activeCount };
}
