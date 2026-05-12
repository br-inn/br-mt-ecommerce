"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  productsApi,
  type Product,
  type ProductCreatePayload,
  type ProductListItem,
  type ProductListResponse,
  type ProductUpdatePayload,
} from "@/lib/api/endpoints/products";
import { productKeys } from "./query-keys";

interface ListPagesData {
  pages: ProductListResponse[];
  pageParams: (string | null)[];
}

export function useCreateProduct() {
  const qc = useQueryClient();
  return useMutation<Product, Error, ProductCreatePayload>({
    mutationFn: (payload) => productsApi.create(payload),
    onSuccess: (created) => {
      // Sembrar caché del detalle para evitar refetch inmediato.
      const id =
        (created as Product & { id?: string }).id ?? created.internal_id;
      qc.setQueryData(productKeys.detail(id), created);
      qc.setQueryData(productKeys.detail(created.sku), created);
      void qc.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}

export function useUpdateProduct(idOrSku: string) {
  const qc = useQueryClient();
  return useMutation<
    Product,
    Error,
    ProductUpdatePayload,
    { previous: Product | undefined }
  >({
    mutationFn: (payload) => productsApi.update(idOrSku, payload),
    onMutate: async (payload) => {
      // Optimistic update sobre el detalle.
      await qc.cancelQueries({ queryKey: productKeys.detail(idOrSku) });
      const previous = qc.getQueryData<Product>(productKeys.detail(idOrSku));
      if (previous) {
        qc.setQueryData<Product>(productKeys.detail(idOrSku), {
          ...previous,
          ...payload,
        } as Product);
      }
      return { previous };
    },
    onError: (_err, _payload, ctx) => {
      if (ctx?.previous) {
        qc.setQueryData(productKeys.detail(idOrSku), ctx.previous);
      }
    },
    onSuccess: (updated) => {
      const id =
        (updated as Product & { id?: string }).id ?? updated.internal_id;
      qc.setQueryData(productKeys.detail(id), updated);
      qc.setQueryData(productKeys.detail(updated.sku), updated);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}

export function useDeleteProduct() {
  const qc = useQueryClient();
  return useMutation<void, Error, string>({
    mutationFn: (id) => productsApi.remove(id),
    onSuccess: (_, id) => {
      qc.removeQueries({ queryKey: productKeys.detail(id) });
      void qc.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}

/**
 * Toggle optimista del flag `active` en lista + detalle.
 *
 * Post-Fase B: `active` es un computed read-only en backend, derivado de
 * `lifecycle_status === 'active'`. Para mutarlo, enviamos `lifecycle_status`
 * = `'active'` o `'deprecated'` según el toggle. La caché optimista parchea
 * ambos campos para evitar flickers.
 */
export function useToggleProductActive() {
  const qc = useQueryClient();
  return useMutation<
    Product,
    Error,
    { id: string; active: boolean },
    { previousLists: [readonly unknown[], ListPagesData | undefined][] }
  >({
    mutationFn: ({ id, active }) =>
      productsApi.update(id, {
        lifecycle_status: active ? "active" : "deprecated",
      }),
    onMutate: async ({ id, active }) => {
      await qc.cancelQueries({ queryKey: productKeys.lists() });
      const previousLists = qc.getQueriesData<ListPagesData>({ queryKey: productKeys.lists() });
      const nextLifecycle = active ? "active" : "deprecated";
      previousLists.forEach(([key, data]) => {
        if (!data) return;
        qc.setQueryData<ListPagesData>(key, {
          ...data,
          pages: data.pages.map((page) => ({
            ...page,
            items: page.items.map((it: ProductListItem) =>
              (it as ProductListItem & { id?: string }).id === id
                ? { ...it, active, lifecycle_status: nextLifecycle }
                : it,
            ),
          })),
        });
      });
      return { previousLists };
    },
    onError: (_err, _payload, ctx) => {
      ctx?.previousLists.forEach(([key, data]) => {
        if (data) qc.setQueryData(key, data);
      });
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: productKeys.lists() });
    },
  });
}
