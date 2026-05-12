"use client";

import { useQuery } from "@tanstack/react-query";
import { dimensionsApi } from "@/lib/api/endpoints/dimensions";
import type {
  ActuationCode,
  DimensionTableResponse,
  PressureTemperatureCurveResponse,
  Standard,
} from "@/lib/api/types-dimensions";

/**
 * TanStack Query hooks for Fase 3 granular technical-table endpoints.
 *
 * Query-key conventions:
 *   ['dimensions', 'product', sku]             — product dimension table
 *   ['pressure-temperature', sku, variant?]    — product P-T curve
 *   ['actuation-codes']                         — catalogue
 *   ['standards']                               — catalogue
 */

export const dimensionsKeys = {
  productDimensions: (sku: string) =>
    ["dimensions", "product", sku] as const,
  productPressureTemperature: (sku: string, variant?: string) =>
    ["pressure-temperature", sku, variant ?? null] as const,
  actuationCodes: () => ["actuation-codes"] as const,
  standards: () => ["standards"] as const,
};

/**
 * `useProductDimensions(sku)` — fetch the full dimension table (columns ×
 * rows × cells) for a product. Disabled when `sku` is falsy.
 */
export function useProductDimensions(sku: string | undefined) {
  return useQuery<DimensionTableResponse, Error>({
    queryKey: dimensionsKeys.productDimensions(sku ?? ""),
    queryFn: () => dimensionsApi.getProductDimensions(sku as string),
    enabled: !!sku,
    staleTime: 60_000,
  });
}

/**
 * `useProductPressureTemperature(sku, variant?)` — fetch the P-T curve for
 * a product, optionally filtered by `series_variant_code`. Disabled when
 * `sku` is falsy.
 */
export function useProductPressureTemperature(
  sku: string | undefined,
  seriesVariantCode?: string,
) {
  return useQuery<PressureTemperatureCurveResponse, Error>({
    queryKey: dimensionsKeys.productPressureTemperature(
      sku ?? "",
      seriesVariantCode,
    ),
    queryFn: () =>
      dimensionsApi.getProductPressureTemperature(
        sku as string,
        seriesVariantCode,
      ),
    enabled: !!sku,
    staleTime: 60_000,
  });
}

/**
 * `useActuationCodes()` — curated catalogue of actuation codes. Long stale
 * time because the catalogue rarely changes within a session.
 */
export function useActuationCodes() {
  return useQuery<ActuationCode[], Error>({
    queryKey: dimensionsKeys.actuationCodes(),
    queryFn: () => dimensionsApi.listActuationCodes(),
    staleTime: 5 * 60_000,
  });
}

/**
 * `useStandards()` — list of standards.
 */
export function useStandards() {
  return useQuery<Standard[], Error>({
    queryKey: dimensionsKeys.standards(),
    queryFn: () => dimensionsApi.listStandards(),
    staleTime: 5 * 60_000,
  });
}
