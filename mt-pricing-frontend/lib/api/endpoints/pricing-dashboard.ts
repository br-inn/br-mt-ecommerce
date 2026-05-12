"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Wrapper tipado para el endpoint `/api/v1/dashboard/pricing-stats`.
 *
 * Mismo patrón que `dashboard.ts`: fetch con Bearer del access_token vivo.
 * Frontend refresca cada 60s via `refetchInterval`.
 */

// ---- Types ----------------------------------------------------------------

export interface ExceptionRuleHit {
  rule_code: string;
  channel_id: string | null;
  scheme_code: string | null;
  count: number;
}

export interface DailyPricingTrend {
  date: string;
  auto_approved: number;
  manual_approved: number;
  pending: number;
}

export interface PricingDashboardStats {
  pending_review_count: number;
  auto_approved_count: number;
  approved_today_count: number;
  escalated_count: number;
  avg_approval_lag_hours: number;
  top_exception_rules: ExceptionRuleHit[];
  daily_trend: DailyPricingTrend[];
  as_of: string;
}

// ---- Fetcher --------------------------------------------------------------

async function authedFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  const headers = new Headers(init.headers);
  headers.set("Content-Type", "application/json");
  if (session?.access_token) {
    headers.set("Authorization", `Bearer ${session.access_token}`);
  }
  const res = await fetch(`${env.NEXT_PUBLIC_BACKEND_URL}${path}`, {
    ...init,
    headers,
    cache: "no-store",
  });
  if (!res.ok) {
    let detail: unknown = undefined;
    try {
      detail = await res.json();
    } catch {
      // ignore
    }
    const message =
      typeof detail === "object" && detail !== null && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export const pricingDashboardApi = {
  getStats: (): Promise<PricingDashboardStats> =>
    authedFetch<PricingDashboardStats>("/api/v1/dashboard/pricing-stats"),
};
