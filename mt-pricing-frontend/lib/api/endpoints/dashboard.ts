"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Wrapper tipado para el endpoint `/api/v1/dashboard/stats`.
 *
 * Mismo patrón que `auth.ts`: `fetch` con Bearer del access_token vivo.
 */

// ---- Types ----------------------------------------------------------------

export interface CatalogStats {
  products_total: number;
  products_active: number;
  products_complete: number;
  products_partial: number;
  products_blocked: number;
}

export interface TranslationStats {
  es_approved: number;
  ar_approved: number;
  es_coverage_pct: number;
  ar_coverage_pct: number;
}

export interface UserStatsKPI {
  total: number;
  with_role: number;
  without_role: number;
}

export interface RecentEvent {
  id: string;
  actor_id: string | null;
  entity_type: string;
  action: string;
  event_at: string;
}

export interface ActivityStats {
  audit_events_24h: number;
  recent_events: RecentEvent[];
}

export interface JobStats {
  enabled: number;
  runs_24h: number;
  failures_24h: number;
}

export interface DashboardStats {
  catalog: CatalogStats;
  translations: TranslationStats;
  users: UserStatsKPI;
  activity: ActivityStats;
  jobs: JobStats;
  as_of: string;
}

// ---- Fetcher --------------------------------------------------------------

async function authedFetch<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
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
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText;
    throw new Error(message);
  }
  return (await res.json()) as T;
}

export const dashboardApi = {
  getStats: (): Promise<DashboardStats> =>
    authedFetch<DashboardStats>("/api/v1/dashboard/stats"),
};
