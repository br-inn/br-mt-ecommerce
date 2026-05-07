"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  fxRatesApi,
  type FXRateCreatePayload,
  type FXRateFilters,
  type FXRateRow,
} from "@/lib/api/endpoints/fx-rates";

const KEYS = {
  all: () => ["fx-rates-admin"] as const,
  list: (filters: FXRateFilters) => [...KEYS.all(), "list", filters] as const,
};

/** Lista de FX rates (todas o filtradas). */
export function useFxRatesAdmin(filters: FXRateFilters = {}) {
  return useQuery<FXRateRow[], Error>({
    queryKey: KEYS.list(filters),
    queryFn: () => fxRatesApi.list(filters),
    staleTime: 30_000,
  });
}

/** Crea FX rate — el trigger SQL cierra el rate previo automáticamente. */
export function useCreateFxRateAdmin() {
  const qc = useQueryClient();
  return useMutation<FXRateRow, Error, FXRateCreatePayload>({
    mutationFn: (payload) => fxRatesApi.create(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
      // Legacy hook (admin/divisas viejo) consume `["fx", "rates"]`.
      void qc.invalidateQueries({ queryKey: ["fx", "rates"] });
    },
  });
}

export const fxRatesQueryKeys = KEYS;
