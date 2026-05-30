"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  costsApi,
  type Cost,
  type CostCreatePayload,
  type CostCreatedResponse,
  type CostFilters,
  type CostMissingItem,
  type CostPatchPayload,
  type CostUpdatePayload,
  type CostsListResponse,
} from "@/lib/api/endpoints/costs";
import { costKeys } from "./query-keys";

const DEFAULT_LIMIT = 50;

/** Lista paginada cursor-based de costs (acepta filtros por sku/scheme/supplier). */
export function useCosts(filters: CostFilters = {}) {
  return useInfiniteQuery<
    CostsListResponse,
    Error,
    { pages: CostsListResponse[]; pageParams: (string | null)[] },
    ReturnType<typeof costKeys.list>,
    string | null
  >({
    queryKey: costKeys.list(filters),
    queryFn: ({ pageParam }) =>
      costsApi.list({
        ...filters,
        cursor: pageParam,
        limit: filters.limit ?? DEFAULT_LIMIT,
      }),
    initialPageParam: null,
    getNextPageParam: (last) => last.cursor?.next ?? undefined,
    staleTime: 30_000,
  });
}

/** GET /products/{sku}/costs — costes vigentes del SKU agrupados por scheme. */
export function useCostsForSku(
  sku: string | undefined,
  asOf?: string,
  onlyActive = true,
  enabled = true,
) {
  return useQuery<Cost[], Error>({
    queryKey: [
      ...costKeys.all(),
      "sku",
      sku ?? "",
      { asOf: asOf ?? null, onlyActive },
    ] as const,
    queryFn: () => costsApi.listForSku(sku as string, asOf, onlyActive),
    enabled: enabled && !!sku,
    staleTime: 30_000,
  });
}

/**
 * GET /costs/as-of — coste vigente a una fecha para sku+scheme(+supplier).
 * Deshabilitado hasta que sku, scheme_code y date estén presentes.
 */
export function useCostAsOf(
  params: {
    sku: string | undefined;
    scheme_code: string | undefined;
    supplier_code?: string | null | undefined;
    date: string | undefined;
  },
  enabled = true,
) {
  const { sku, scheme_code, supplier_code, date } = params;
  const ready = !!sku && !!scheme_code && !!date;
  return useQuery<Cost, Error>({
    queryKey: [
      ...costKeys.all(),
      "as-of",
      { sku: sku ?? "", scheme_code: scheme_code ?? "", supplier_code: supplier_code ?? null, date: date ?? "" },
    ] as const,
    queryFn: () =>
      costsApi.asOf({
        sku: sku as string,
        scheme_code: scheme_code as string,
        supplier_code: supplier_code ?? undefined,
        date: date as string,
      }),
    enabled: enabled && ready,
    staleTime: 30_000,
  });
}

export function useCost(id: string | undefined, enabled = true) {
  return useQuery<Cost, Error>({
    queryKey: costKeys.detail(id ?? ""),
    queryFn: () => costsApi.get(id as string),
    enabled: enabled && !!id,
    staleTime: 60_000,
  });
}

/** POST motor nuevo — devuelve `{ cost, warnings }`. */
export function useCreateCost() {
  const qc = useQueryClient();
  return useMutation<CostCreatedResponse, Error, CostCreatePayload>({
    mutationFn: (payload) => costsApi.create(payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: costKeys.all() });
    },
  });
}

/** PUT corrección in-place — devuelve `{ cost, warnings }`. */
export function useUpdateCost(id: string) {
  const qc = useQueryClient();
  return useMutation<CostCreatedResponse, Error, CostUpdatePayload>({
    mutationFn: (payload) => costsApi.update(id, payload),
    onSuccess: (resp) => {
      qc.setQueryData(costKeys.detail(resp.cost.id), resp.cost);
      void qc.invalidateQueries({ queryKey: costKeys.all() });
    },
  });
}

/**
 * POST /costs/{id}/close — fija `valid_to` (descatalogar / cierre sin sucesor).
 * Invalida los listados y el detalle del coste cerrado.
 */
export function useCloseCost() {
  const qc = useQueryClient();
  return useMutation<Cost, Error, { id: string; valid_to: string }>({
    mutationFn: ({ id, valid_to }) => costsApi.close(id, valid_to),
    onSuccess: (updated) => {
      qc.setQueryData(costKeys.detail(updated.id), updated);
      void qc.invalidateQueries({ queryKey: costKeys.lists() });
      void qc.invalidateQueries({ queryKey: costKeys.detail(updated.id) });
    },
  });
}

export function usePatchCost(id: string) {
  const qc = useQueryClient();
  return useMutation<Cost, Error, CostPatchPayload>({
    mutationFn: (payload) => costsApi.patch(id, payload),
    onSuccess: (updated) => {
      qc.setQueryData(costKeys.detail(updated.id), updated);
      void qc.invalidateQueries({ queryKey: costKeys.lists() });
    },
  });
}

export function useDeleteCost() {
  const qc = useQueryClient();
  return useMutation<void, Error, { id: string }>({
    mutationFn: ({ id }) => costsApi.delete(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: costKeys.all() });
    },
  });
}

/** GET /costs/missing — para Champion / dashboard "SKUs sin coste". */
export function useMissingCosts(
  schemeCode: string | undefined,
  enabled = true,
) {
  return useQuery<CostMissingItem[], Error>({
    queryKey: [...costKeys.all(), "missing", schemeCode ?? ""] as const,
    queryFn: () => costsApi.missingForScheme(schemeCode as string),
    enabled: enabled && !!schemeCode,
    staleTime: 60_000,
  });
}
