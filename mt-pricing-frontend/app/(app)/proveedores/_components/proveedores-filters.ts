"use client";

import { useSearchParams, useRouter, usePathname } from "next/navigation";
import { useCallback, useMemo } from "react";

/** Filtros listado `/proveedores` con estado en URL. */
export interface ProveedoresListFilters {
  search: string | undefined;
  contract_currency: string | undefined;
  active: boolean | undefined;
}

export type ProveedoresFilterKey = "q" | "contract_currency" | "active";

export function useProveedoresListFilters() {
  const sp = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();

  const filters: ProveedoresListFilters = useMemo(() => {
    const activeRaw = sp.get("active");
    const active =
      activeRaw === "true" ? true : activeRaw === "false" ? false : undefined;
    return {
      search: sp.get("q") ?? undefined,
      contract_currency: sp.get("contract_currency") ?? undefined,
      active,
    };
  }, [sp]);

  const setFilter = useCallback(
    (key: ProveedoresFilterKey, value: string | undefined) => {
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
    filters.search || filters.contract_currency || filters.active !== undefined,
  );

  return { filters, setFilter, clear, hasFilters };
}
