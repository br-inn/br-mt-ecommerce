"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  productsApi,
  type Language,
  type ProductTranslationRead,
  type TranslationUpsertPayload,
} from "@/lib/api/endpoints/products";
import { productKeys } from "./query-keys";

export function useProductTranslations(productId: string | undefined) {
  return useQuery<ProductTranslationRead[], Error>({
    queryKey: productKeys.translations(productId ?? ""),
    queryFn: () => productsApi.listTranslations(productId as string),
    enabled: !!productId,
    staleTime: 30_000,
  });
}

export function useUpsertTranslation(productId: string) {
  const qc = useQueryClient();
  return useMutation<
    ProductTranslationRead,
    Error,
    { lang: Language; payload: TranslationUpsertPayload }
  >({
    mutationFn: ({ lang, payload }) => productsApi.upsertTranslation(productId, lang, payload),
    onSuccess: (translation) => {
      qc.setQueryData<ProductTranslationRead[]>(
        productKeys.translations(productId),
        (prev) => {
          if (!prev) return [translation];
          const idx = prev.findIndex((t) => t.language === translation.language);
          if (idx === -1) return [...prev, translation];
          const out = [...prev];
          out[idx] = translation;
          return out;
        },
      );
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });
}

export function useApproveTranslation(productId: string) {
  const qc = useQueryClient();
  return useMutation<ProductTranslationRead, Error, Language>({
    mutationFn: (lang) => productsApi.approveTranslation(productId, lang),
    onSuccess: (translation) => {
      qc.setQueryData<ProductTranslationRead[]>(
        productKeys.translations(productId),
        (prev) => {
          if (!prev) return [translation];
          return prev.map((t) => (t.language === translation.language ? translation : t));
        },
      );
      void qc.invalidateQueries({ queryKey: productKeys.detail(productId) });
    },
  });
}
