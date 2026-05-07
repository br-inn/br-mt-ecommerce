"use client";

import {
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  fxApi,
  type Currency,
  type FXRate,
  type FXRateCreatePayload,
  type FXRateFilters,
} from "@/lib/api/endpoints/fx";

const KEYS = {
  currencies: () => ["fx", "currencies"] as const,
  rates: (filters: FXRateFilters) => ["fx", "rates", filters] as const,
};

export function useCurrencies() {
  return useQuery<Currency[], Error>({
    queryKey: KEYS.currencies(),
    queryFn: () => fxApi.listCurrencies(),
    staleTime: 5 * 60_000,
  });
}

export function useFxRates(filters: FXRateFilters = {}) {
  return useQuery<FXRate[], Error>({
    queryKey: KEYS.rates(filters),
    queryFn: () => fxApi.listRates(filters),
    staleTime: 30_000,
  });
}

export function useCreateFxRate() {
  const qc = useQueryClient();
  return useMutation<FXRate, Error, FXRateCreatePayload>({
    mutationFn: (payload) => fxApi.createRate(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["fx", "rates"] });
    },
  });
}
