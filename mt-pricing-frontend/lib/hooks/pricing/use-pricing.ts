"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { toast } from "sonner";

import {
  pricingApi,
  type Channel,
  type PriceDetail,
  type PriceFilters,
  type PriceListResponse,
  type PriceProposePayload,
  type PriceRow,
  type PriceSimulatePayload,
  type PricingResult,
} from "@/lib/api/endpoints/pricing";

// ---- Query keys -----------------------------------------------------------

export const pricingKeys = {
  all: ["pricing"] as const,
  prices: (filters: PriceFilters) =>
    ["pricing", "prices", filters] as const,
  detail: (id: string) => ["pricing", "prices", id] as const,
  channels: (state?: string | undefined) =>
    ["pricing", "channels", state ?? "all"] as const,
};

const DEFAULT_LIMIT = 25;

// ---- Reads ----------------------------------------------------------------

export function usePrices(filters: PriceFilters = {}) {
  return useInfiniteQuery<
    PriceListResponse,
    Error,
    { pages: PriceListResponse[]; pageParams: (string | null)[] },
    ReturnType<typeof pricingKeys.prices>,
    string | null
  >({
    queryKey: pricingKeys.prices(filters),
    queryFn: ({ pageParam }) =>
      pricingApi.list({
        ...filters,
        cursor: pageParam,
        limit: filters.limit ?? DEFAULT_LIMIT,
      }),
    initialPageParam: null,
    getNextPageParam: (last) => last.cursor.next ?? undefined,
    staleTime: 15_000,
  });
}

export function usePriceDetail(id: string | undefined) {
  return useQuery<PriceDetail, Error>({
    queryKey: pricingKeys.detail(id ?? ""),
    queryFn: () => pricingApi.get(id as string),
    enabled: !!id,
    staleTime: 15_000,
  });
}

export function useChannels(state?: string) {
  return useQuery<Channel[], Error>({
    queryKey: pricingKeys.channels(state),
    queryFn: () => pricingApi.channels(state),
    staleTime: 5 * 60_000,
  });
}

// ---- Mutations ------------------------------------------------------------

export function useSimulatePrice() {
  return useMutation<PricingResult, Error, PriceSimulatePayload>({
    mutationFn: (payload) => pricingApi.simulate(payload),
    onError: (e) => toast.error(`Simulación falló: ${e.message}`),
  });
}

export function useProposePrice() {
  const qc = useQueryClient();
  return useMutation<PriceRow, Error, PriceProposePayload>({
    mutationFn: (payload) => pricingApi.propose(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: pricingKeys.all });
      toast.success("Propuesta enviada a aprobación");
    },
    onError: (e) => toast.error(`No se pudo proponer: ${e.message}`),
  });
}

export function useApprovePrice() {
  const qc = useQueryClient();
  return useMutation<PriceRow, Error, { id: string; reason?: string }>({
    mutationFn: ({ id, reason }) => pricingApi.approve(id, reason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: pricingKeys.all });
      toast.success("Propuesta aprobada");
    },
    onError: (e) => toast.error(`No se pudo aprobar: ${e.message}`),
  });
}

export function useRejectPrice() {
  const qc = useQueryClient();
  return useMutation<PriceRow, Error, { id: string; reason: string }>({
    mutationFn: ({ id, reason }) => pricingApi.reject(id, reason),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: pricingKeys.all });
      toast.success("Propuesta rechazada");
    },
    onError: (e) => toast.error(`No se pudo rechazar: ${e.message}`),
  });
}

export function useBulkApprovePrices() {
  const qc = useQueryClient();
  // Nota: backend usa `comment` (no `reason`) — campo obligatorio ≥10 chars.
  return useMutation<unknown, Error, { ids: string[]; comment?: string }>({
    mutationFn: ({ ids, comment }) => pricingApi.bulkApprove(ids, comment),
    onSuccess: (_data, vars) => {
      void qc.invalidateQueries({ queryKey: pricingKeys.all });
      toast.success(`${vars.ids.length} propuestas aprobadas`);
    },
    onError: (e) => toast.error(`Bulk-approve falló: ${e.message}`),
  });
}

export function useRecalculatePrices() {
  return useMutation<{ task_id: string; status: string }, Error, void>({
    mutationFn: () => pricingApi.recalcAll(),
    onSuccess: (data) => toast.success(`Recálculo encolado · job ${data.task_id}`),
    onError: (e) => toast.error(`Recálculo falló: ${e.message}`),
  });
}
