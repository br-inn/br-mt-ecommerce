"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  productsApi,
  type ImageConfirmPayload,
  type ProductAsset,
  type UploadUrlResponse,
} from "@/lib/api/endpoints/products";
import { productKeys } from "./query-keys";

export function useProductImages(productId: string | undefined) {
  return useQuery<ProductAsset[], Error>({
    queryKey: productKeys.images(productId ?? ""),
    queryFn: () => productsApi.listImages(productId as string),
    enabled: !!productId,
    staleTime: 30_000,
  });
}

export function useGetUploadUrl(productId: string) {
  return useMutation<UploadUrlResponse, Error, { fileName: string; contentType: string }>({
    mutationFn: ({ fileName, contentType }) =>
      productsApi.getUploadUrl(productId, fileName, contentType),
  });
}

export function useConfirmImageUpload(productId: string) {
  const qc = useQueryClient();
  return useMutation<ProductAsset, Error, ImageConfirmPayload>({
    mutationFn: (payload) => productsApi.confirmImageUpload(productId, payload),
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: productKeys.images(productId) });
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });
}

export function useSetPrimaryImage(productId: string) {
  const qc = useQueryClient();
  return useMutation<
    ProductAsset,
    Error,
    string,
    { previous: ProductAsset[] | undefined }
  >({
    mutationFn: (imageId) => productsApi.setPrimaryImage(productId, imageId),
    onMutate: async (imageId) => {
      await qc.cancelQueries({ queryKey: productKeys.images(productId) });
      const previous = qc.getQueryData<ProductAsset[]>(productKeys.images(productId));
      if (previous) {
        qc.setQueryData<ProductAsset[]>(
          productKeys.images(productId),
          previous.map((img) => ({ ...img, is_primary: img.id === imageId })),
        );
      }
      return { previous };
    },
    onError: (_err, _imageId, ctx) => {
      if (ctx?.previous) qc.setQueryData(productKeys.images(productId), ctx.previous);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: productKeys.images(productId) });
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });
}

export function useDeleteImage(productId: string) {
  const qc = useQueryClient();
  return useMutation<void, Error, string, { previous: ProductAsset[] | undefined }>({
    mutationFn: (imageId) => productsApi.deleteImage(productId, imageId),
    onMutate: async (imageId) => {
      await qc.cancelQueries({ queryKey: productKeys.images(productId) });
      const previous = qc.getQueryData<ProductAsset[]>(productKeys.images(productId));
      if (previous) {
        qc.setQueryData<ProductAsset[]>(
          productKeys.images(productId),
          previous.filter((img) => img.id !== imageId),
        );
      }
      return { previous };
    },
    onError: (_err, _imageId, ctx) => {
      if (ctx?.previous) qc.setQueryData(productKeys.images(productId), ctx.previous);
    },
    onSettled: () => {
      void qc.invalidateQueries({ queryKey: productKeys.images(productId) });
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });
}
