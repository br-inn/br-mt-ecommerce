"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type {
  ActuationCode,
  DimensionTableResponse,
  PressureTemperatureCurveResponse,
  Standard,
} from "@/lib/api/types-dimensions";

/**
 * Typed wrappers for Fase 3 granular technical-table endpoints.
 *
 * Backend reference: `mt-pricing-backend/app/api/routes/dimensions.py`.
 */

// ---------------------------------------------------------------------------
// Errors + auth helper (mirrors lib/api/endpoints/attributes.ts pattern)
// ---------------------------------------------------------------------------

export class DimensionsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "DimensionsApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  if (!headers.has("Content-Type") && init.body) {
    headers.set("Content-Type", "application/json");
  }
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  const res = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      /* noop */
    }
    throw new DimensionsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

/**
 * `GET /api/v1/products/{sku}/dimensions` — full dimension table for a
 * product (columns × rows × cells nested).
 */
export async function getProductDimensions(
  sku: string,
): Promise<DimensionTableResponse> {
  return authedFetch<DimensionTableResponse>(
    `/api/v1/products/${encodeURIComponent(sku)}/dimensions`,
  );
}

/**
 * `GET /api/v1/products/{sku}/pressure-temperature` — P-T curve points for
 * a product. Optionally filter by `series_variant_code`.
 */
export async function getProductPressureTemperature(
  sku: string,
  seriesVariantCode?: string,
): Promise<PressureTemperatureCurveResponse> {
  const params = new URLSearchParams();
  if (seriesVariantCode) {
    params.set("series_variant_code", seriesVariantCode);
  }
  const qs = params.toString();
  return authedFetch<PressureTemperatureCurveResponse>(
    `/api/v1/products/${encodeURIComponent(sku)}/pressure-temperature${qs ? `?${qs}` : ""}`,
  );
}

/**
 * `GET /api/v1/actuation-codes` — curated catalogue of actuation codes.
 */
export async function listActuationCodes(): Promise<ActuationCode[]> {
  return authedFetch<ActuationCode[]>(`/api/v1/actuation-codes`);
}

/**
 * `GET /api/v1/standards` — list standards (ASTM, EN, ISO…).
 */
export async function listStandards(): Promise<Standard[]> {
  return authedFetch<Standard[]>(`/api/v1/standards`);
}

export const dimensionsApi = {
  getProductDimensions,
  getProductPressureTemperature,
  listActuationCodes,
  listStandards,
};
