"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// ── Types ─────────────────────────────────────────────────────────────────────

export interface MarketStats {
  avg_price_aed: number | null;
  min_price_aed: number | null;
  max_price_aed: number | null;
}

export interface PriceKpis {
  price_gap_pct: number | null;
  price_index_base: number | null;
  price_position_index: number | null;
}

export interface DashboardResponse {
  date_from: string;
  date_to: string;
  marketplace: string | null;
  brand_id: string | null;
  total_records: number;
  market_stats: MarketStats;
  kpis: PriceKpis;
  note?: string;
}

export interface HistogramBin {
  bin: string;
  count: number;
}

export interface QualityResponse {
  period_days: number;
  histogram: HistogramBin[];
  median_confidence: number | null;
  pct_above_80: number | null;
  total: number;
  total_with_confidence: number;
}

export interface ListingItem {
  candidate_id: string;
  sku: string;
  marketplace: string;
  competitor_title: string;
  competitor_price_aed: number | null;
  score: number;
  status: string;
  calibrated_confidence: number | null;
}

export interface ListingsResponse {
  brand_id: string;
  total: number;
  limit: number;
  offset: number;
  listings: ListingItem[];
}

// ── API helpers ───────────────────────────────────────────────────────────────

async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) throw new Error("Not authenticated");
  return {
    Authorization: `Bearer ${session.access_token}`,
    "Content-Type": "application/json",
  };
}

const BASE = env.NEXT_PUBLIC_API_URL ?? "";

export async function fetchPriceIntelligenceDashboard(params: {
  brandId?: string;
  marketplace?: string;
  dateFrom?: string;
  dateTo?: string;
}): Promise<DashboardResponse> {
  const headers = await getAuthHeaders();
  const q = new URLSearchParams();
  if (params.brandId) q.set("brand_id", params.brandId);
  if (params.marketplace) q.set("marketplace", params.marketplace);
  if (params.dateFrom) q.set("date_from", params.dateFrom);
  if (params.dateTo) q.set("date_to", params.dateTo);
  const res = await fetch(`${BASE}/api/v1/price-intelligence/dashboard?${q.toString()}`, { headers });
  if (!res.ok) throw new Error(`Dashboard fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchPriceIntelligenceQuality(): Promise<QualityResponse> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE}/api/v1/price-intelligence/quality`, { headers });
  if (!res.ok) throw new Error(`Quality fetch failed: ${res.status}`);
  return res.json();
}

export async function fetchBrandListings(
  brandId: string,
  params?: { marketplace?: string; limit?: number; offset?: number }
): Promise<ListingsResponse> {
  const headers = await getAuthHeaders();
  const q = new URLSearchParams();
  if (params?.marketplace) q.set("marketplace", params.marketplace);
  if (params?.limit) q.set("limit", String(params.limit));
  if (params?.offset) q.set("offset", String(params.offset));
  const res = await fetch(`${BASE}/api/v1/price-intelligence/listings/${brandId}?${q.toString()}`, {
    headers,
  });
  if (!res.ok) throw new Error(`Listings fetch failed: ${res.status}`);
  return res.json();
}
