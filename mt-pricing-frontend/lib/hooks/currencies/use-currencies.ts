"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";

import {
  currenciesApi,
  type CurrencyActivePatchPayload,
  type CurrencyAdmin,
} from "@/lib/api/endpoints/currencies";

const KEYS = {
  all: () => ["currencies-admin"] as const,
  list: () => [...KEYS.all(), "list"] as const,
};

/** Lista de currencies (incluye inactivas) — usado por el admin. */
export function useCurrenciesAdmin() {
  return useQuery<CurrencyAdmin[], Error>({
    queryKey: KEYS.list(),
    queryFn: () => currenciesApi.list(),
    staleTime: 60_000,
  });
}

/** Activa/desactiva una currency. Refresca la lista on success. */
export function useSetCurrencyActive() {
  const qc = useQueryClient();
  return useMutation<
    CurrencyAdmin,
    Error,
    { code: string; payload: CurrencyActivePatchPayload }
  >({
    mutationFn: ({ code, payload }) => currenciesApi.setActive(code, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: KEYS.all() });
      // El componente legacy `useCurrencies` (lib/hooks/fx) consume el endpoint
      // pricing.* — invalidamos también esa cache para mantener consistencia.
      void qc.invalidateQueries({ queryKey: ["fx", "currencies"] });
    },
  });
}

export const currenciesQueryKeys = KEYS;
