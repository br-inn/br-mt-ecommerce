"use client";

import {
  useInfiniteQuery,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  suppliersApi,
  type Supplier,
  type SupplierCreatePayload,
  type SupplierFilters,
  type SupplierListResponse,
  type SupplierPatchPayload,
} from "@/lib/api/endpoints/suppliers";
import { supplierKeys } from "./query-keys";

const DEFAULT_LIMIT = 25;

/** Lista paginada cursor-based de proveedores. */
export function useSuppliers(filters: SupplierFilters = {}) {
  return useInfiniteQuery<
    SupplierListResponse,
    Error,
    { pages: SupplierListResponse[]; pageParams: (string | null)[] },
    ReturnType<typeof supplierKeys.list>,
    string | null
  >({
    queryKey: supplierKeys.list(filters),
    queryFn: ({ pageParam }) =>
      suppliersApi.list({
        ...filters,
        cursor: pageParam,
        limit: filters.limit ?? DEFAULT_LIMIT,
      }),
    initialPageParam: null,
    getNextPageParam: (last) => last.cursor?.next ?? undefined,
    staleTime: 30_000,
  });
}

export function useSupplier(code: string | undefined, enabled = true) {
  return useQuery<Supplier, Error>({
    queryKey: supplierKeys.detail(code ?? ""),
    queryFn: () => suppliersApi.get(code as string),
    enabled: enabled && !!code,
    staleTime: 60_000,
  });
}

export function useCreateSupplier() {
  const qc = useQueryClient();
  return useMutation<Supplier, Error, SupplierCreatePayload>({
    mutationFn: (payload) => suppliersApi.create(payload),
    onSuccess: (created) => {
      qc.setQueryData(supplierKeys.detail(created.code), created);
      void qc.invalidateQueries({ queryKey: supplierKeys.lists() });
    },
  });
}

export function usePatchSupplier(code: string) {
  const qc = useQueryClient();
  return useMutation<
    Supplier,
    Error,
    SupplierPatchPayload,
    { previous: Supplier | undefined }
  >({
    mutationFn: (payload) => suppliersApi.patch(code, payload),
    onMutate: async (payload) => {
      // Optimistic update sobre el detail.
      await qc.cancelQueries({ queryKey: supplierKeys.detail(code) });
      const previous = qc.getQueryData<Supplier>(supplierKeys.detail(code));
      if (previous) {
        qc.setQueryData<Supplier>(supplierKeys.detail(code), {
          ...previous,
          ...payload,
        } as Supplier);
      }
      return { previous };
    },
    onError: (_err, _payload, ctx) => {
      if (ctx?.previous) qc.setQueryData(supplierKeys.detail(code), ctx.previous);
    },
    onSuccess: (updated) => {
      qc.setQueryData(supplierKeys.detail(updated.code), updated);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: supplierKeys.lists() });
    },
  });
}

/** Soft-delete (PATCH active=false). Mantiene el row para audit/VAT-compliance. */
export function useToggleSupplierActive() {
  const qc = useQueryClient();
  return useMutation<Supplier, Error, { code: string; active: boolean }>({
    mutationFn: ({ code, active }) => suppliersApi.setActive(code, active),
    onSuccess: (updated) => {
      qc.setQueryData(supplierKeys.detail(updated.code), updated);
      void qc.invalidateQueries({ queryKey: supplierKeys.lists() });
    },
  });
}

/** Alias retro-compat: el código legacy importa `useUpdateSupplier`. */
export const useUpdateSupplier = usePatchSupplier;
