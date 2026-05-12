"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  attributesApi,
  AttributesApiError,
} from "@/lib/api/endpoints/attributes";
import type {
  AttributeValue,
  AttributeValueUpsertPayload,
  FamilyAttribute,
} from "@/lib/api/types-attributes";

/**
 * TanStack Query hooks for Fase 2 EAV attributes.
 *
 * Query-key conventions:
 *   ['product-attributes', sku]               — product attribute values
 *   ['family-attributes',  familyId]          — family attribute template
 */

export const attributeKeys = {
  productAll: () => ["product-attributes"] as const,
  product: (sku: string) => ["product-attributes", sku] as const,
  familyAll: () => ["family-attributes"] as const,
  family: (familyId: string) => ["family-attributes", familyId] as const,
};

/**
 * `useProductAttributes(sku)` — fetch attribute values for a product.
 *
 * Disabled when `sku` is falsy. Stable 60s stale-time matches the rest of
 * the product hooks in this app.
 */
export function useProductAttributes(sku: string | undefined) {
  return useQuery<AttributeValue[], Error>({
    queryKey: attributeKeys.product(sku ?? ""),
    queryFn: () => attributesApi.listProductAttributeValues(sku as string),
    enabled: !!sku,
    staleTime: 60_000,
  });
}

/**
 * `useFamilyAttributes(familyId)` — fetch the attribute template for a
 * family (with eager AttributeDefinition + enum options).
 *
 * Disabled when `familyId` is falsy.
 */
export function useFamilyAttributes(familyId: string | undefined | null) {
  return useQuery<FamilyAttribute[], Error>({
    queryKey: attributeKeys.family(familyId ?? ""),
    queryFn: () => attributesApi.listFamilyAttributes(familyId as string),
    enabled: !!familyId,
    staleTime: 5 * 60_000,
  });
}

/**
 * `useUpsertProductAttributeValue` — mutation wrapping PUT
 * `/products/{sku}/attributes/{code}`. Invalidates the product's attribute
 * query on success.
 */
export function useUpsertProductAttributeValue(sku: string) {
  const qc = useQueryClient();
  return useMutation<
    AttributeValue,
    AttributesApiError | Error,
    { attrCode: string; payload: AttributeValueUpsertPayload }
  >({
    mutationFn: ({ attrCode, payload }) =>
      attributesApi.upsertProductAttributeValue(sku, attrCode, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: attributeKeys.product(sku) });
    },
  });
}

/**
 * `useDeleteProductAttributeValue` — mutation wrapping DELETE
 * `/products/{sku}/attributes/{code}`. Invalidates the product's attribute
 * query on success.
 */
export function useDeleteProductAttributeValue(sku: string) {
  const qc = useQueryClient();
  return useMutation<void, AttributesApiError | Error, { attrCode: string }>({
    mutationFn: ({ attrCode }) =>
      attributesApi.deleteProductAttributeValue(sku, attrCode),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: attributeKeys.product(sku) });
    },
  });
}
