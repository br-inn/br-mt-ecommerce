"use client";

/**
 * Channel Pricing Desk endpoints — multi-channel B2C/B2B pricing.
 *
 * Reference: docs/superpowers/specs/2026-05-28-channel-pricing-engine-design.md
 * Backend routes: app/api/routes/pricing_desk.py
 */

import { authedFetch } from "@/lib/api/client";
import type { components } from "@/lib/api/types";

// ─── Type aliases ────────────────────────────────────────────────────────────

export type SellingModel = "b2c" | "b2b";
export type FulfillmentScheme =
  | "canal_full"
  | "canal_lastmile"
  | "merchant_managed";
export type Signal = "PÉRDIDA" | "FRÁGIL" | "FINO" | "ÓPTIMO" | "EXCELENTE";

export type PriceResult = components["schemas"]["PriceResultJSON"];
export type CatalogSummary = components["schemas"]["CatalogSummaryResponse"];
export type ProductPriceResponse =
  components["schemas"]["ProductPriceResponse"];
export type OptimizeResponse = components["schemas"]["OptimizeResponse"];
export type TradeRouteParams = components["schemas"]["TradeRouteParamsRead"];
export type TradeRouteParamsUpdate =
  components["schemas"]["TradeRouteParamsUpdate"];
export type ChannelFeeParams = components["schemas"]["ChannelFeeParamsRead"];
export type ChannelFeeParamsUpdate =
  components["schemas"]["ChannelFeeParamsUpdate"];
export type MarginTarget = components["schemas"]["MarginTargetRead"];
export type MarginTargetUpsert = components["schemas"]["MarginTargetUpsert"];
export type MarginOverrideRead = components["schemas"]["MarginOverrideRead"];
export type MarginOverrideUpsert =
  components["schemas"]["MarginOverrideUpsert"];
export type CatalogImportResult =
  components["schemas"]["CatalogImportResult"];

/**
 * ChannelSchemeParamsRead — NOT in generated types.ts (backend exposes inline
 * within /params response). Defined manually to match the backend Pydantic schema.
 */
export interface ChannelSchemeParamsRead {
  id: string;
  channel_id: string;
  fulfillment_scheme: FulfillmentScheme;
  scheme_label: string;
  is_available: boolean;
  flat_supplement_aed: number;
  pct_surcharge: number;
  max_weight_kg: number | null;
}

export interface PricingParamsResponse {
  route: TradeRouteParams;
  fees: ChannelFeeParams & { total_fees_pct: number };
  schemes: ChannelSchemeParamsRead[];
}

// ─── Helper ───────────────────────────────────────────────────────────────────

function buildQuery(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    search.set(k, String(v));
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

// ─── API wrapper ─────────────────────────────────────────────────────────────

export const pricingDeskApi = {
  /** GET /api/v1/pricing/{channel_code}/params */
  async getParams(channelCode: string): Promise<PricingParamsResponse> {
    return authedFetch<PricingParamsResponse>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/params`,
    );
  },

  /** PATCH /api/v1/pricing/{channel_code}/route-params */
  async updateRouteParams(
    channelCode: string,
    body: Partial<TradeRouteParamsUpdate>,
  ): Promise<TradeRouteParams> {
    return authedFetch<TradeRouteParams>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/route-params`,
      { method: "PATCH", body: JSON.stringify(body) },
    );
  },

  /** PATCH /api/v1/pricing/{channel_code}/fee-params */
  async updateFeeParams(
    channelCode: string,
    body: Partial<ChannelFeeParamsUpdate>,
  ): Promise<ChannelFeeParams> {
    return authedFetch<ChannelFeeParams>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/fee-params`,
      { method: "PATCH", body: JSON.stringify(body) },
    );
  },

  /** GET /api/v1/pricing/{channel_code}/margin-targets */
  async listMarginTargets(channelCode: string): Promise<MarginTarget[]> {
    return authedFetch<MarginTarget[]>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/margin-targets`,
    );
  },

  /** PUT /api/v1/pricing/{channel_code}/margin-targets */
  async upsertMarginTarget(
    channelCode: string,
    body: MarginTargetUpsert,
  ): Promise<void> {
    return authedFetch<void>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/margin-targets`,
      { method: "PUT", body: JSON.stringify(body) },
    );
  },

  /** PUT /api/v1/pricing/{channel_code}/margin-overrides/{sku} */
  async upsertMarginOverride(
    channelCode: string,
    sku: string,
    body: MarginOverrideUpsert,
  ): Promise<MarginOverrideRead> {
    return authedFetch<MarginOverrideRead>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/margin-overrides/${encodeURIComponent(sku)}`,
      { method: "PUT", body: JSON.stringify(body) },
    );
  },

  /** DELETE /api/v1/pricing/{channel_code}/margin-overrides/{sku} */
  async deleteMarginOverride(
    channelCode: string,
    sku: string,
    sellingModel: SellingModel = "b2c",
  ): Promise<void> {
    return authedFetch<void>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/margin-overrides/${encodeURIComponent(sku)}${buildQuery({ selling_model: sellingModel })}`,
      { method: "DELETE" },
    );
  },

  /** GET /api/v1/pricing/{channel_code}/product/{sku} */
  async getProductPrice(
    channelCode: string,
    sku: string,
    sellingModel: SellingModel = "b2c",
    marginPct?: number,
  ): Promise<ProductPriceResponse> {
    return authedFetch<ProductPriceResponse>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/product/${encodeURIComponent(sku)}${buildQuery({
        selling_model: sellingModel,
        ...(marginPct !== undefined && { margin_pct: marginPct }),
      })}`,
    );
  },

  /** GET /api/v1/pricing/{channel_code}/catalog */
  async getCatalogSummary(
    channelCode: string,
    options: {
      sellingModel?: SellingModel;
      familyId?: string;
      signal?: string;
    } = {},
  ): Promise<CatalogSummary> {
    return authedFetch<CatalogSummary>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/catalog${buildQuery({
        selling_model: options.sellingModel ?? "b2c",
        ...(options.familyId && { family_id: options.familyId }),
        ...(options.signal && { signal: options.signal }),
      })}`,
    );
  },

  /** POST /api/v1/pricing/{channel_code}/optimize */
  async optimizeCatalog(
    channelCode: string,
    sellingModel: SellingModel = "b2c",
  ): Promise<OptimizeResponse> {
    return authedFetch<OptimizeResponse>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/optimize${buildQuery({ selling_model: sellingModel })}`,
      { method: "POST" },
    );
  },

  /** POST /api/v1/pricing/{channel_code}/optimize/apply */
  async applyOptimization(
    channelCode: string,
    sellingModel: SellingModel = "b2c",
  ): Promise<void> {
    return authedFetch<void>(
      `/api/v1/pricing/${encodeURIComponent(channelCode)}/optimize/apply${buildQuery({ selling_model: sellingModel })}`,
      { method: "POST" },
    );
  },

  /** POST /api/v1/pricing/{channel_code}/catalog/import */
  async importCatalog(
    channelCode: string,
    file: File,
    confirm: boolean = false,
  ): Promise<CatalogImportResult> {
    const supabase = (await import("@/lib/supabase/client")).createSupabaseBrowserClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const formData = new FormData();
    formData.append("file", file);
    const headers = new Headers();
    if (session?.access_token) {
      headers.set("Authorization", `Bearer ${session.access_token}`);
    }
    const { default: env } = await import("@/lib/env");
    const res = await fetch(
      `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/pricing/${encodeURIComponent(channelCode)}/catalog/import${buildQuery({ confirm })}`,
      { method: "POST", headers, body: formData, cache: "no-store" },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => res.statusText);
      throw new Error(
        typeof detail === "string" ? detail : JSON.stringify(detail),
      );
    }
    return (await res.json()) as CatalogImportResult;
  },

  /** POST /api/v1/pricing/{channel_code}/logistics/import */
  async importLogistics(
    channelCode: string,
    file: File,
    confirm: boolean = false,
  ): Promise<{
    total_rows: number;
    upserted: number;
    errors: Array<{ row: number; sku: string; error: string }>;
  }> {
    const supabase = (await import("@/lib/supabase/client")).createSupabaseBrowserClient();
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const formData = new FormData();
    formData.append("file", file);
    const headers = new Headers();
    if (session?.access_token) {
      headers.set("Authorization", `Bearer ${session.access_token}`);
    }
    const { default: env } = await import("@/lib/env");
    const res = await fetch(
      `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/pricing/${encodeURIComponent(channelCode)}/logistics/import${buildQuery({ confirm })}`,
      { method: "POST", headers, body: formData, cache: "no-store" },
    );
    if (!res.ok) {
      const detail = await res.json().catch(() => res.statusText);
      throw new Error(
        typeof detail === "string" ? detail : JSON.stringify(detail),
      );
    }
    return res.json() as Promise<{
      total_rows: number;
      upserted: number;
      errors: Array<{ row: number; sku: string; error: string }>;
    }>;
  },
};
