"use client";

/**
 * Cliente API tipado para la cola de aprobación — US-1B-02-06.
 *
 * Re-usa `authedFetch` y los tipos de `pricing.ts`.
 * Endpoints cubiertos:
 *  - GET  /api/v1/pricing/prices?status=pending_review&...
 *  - POST /api/v1/pricing/prices/{id}/approve
 *  - POST /api/v1/pricing/prices/{id}/reject
 *  - POST /api/v1/pricing/prices/{id}/revise
 *  - POST /api/v1/pricing/prices/bulk-approve   (comment obligatorio ≥10 chars)
 *  - GET  /api/v1/pricing/prices/{id}           (detalle + eventos)
 */

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type {
  PriceRow,
  PriceDetail,
  PriceListResponse,
} from "@/lib/api/endpoints/pricing";

// ---- Re-export types from pricing.ts so callers have a single import -------

export type {
  PriceRow,
  PriceDetail,
  PriceStatus,
  PriceAlert,
  PriceApprovalEvent,
  PriceListResponse,
} from "@/lib/api/endpoints/pricing";

// ---- Filtros cola -----------------------------------------------------------

export interface ApprovalQueueFilters {
  channel?: string | undefined;
  scheme?: string | undefined;
  /** Razón excepción (texto libre, búsqueda parcial) */
  exception_reason?: string | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
  include_total?: boolean | undefined;
}

// ---- Error class -----------------------------------------------------------

export class ApprovalsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(
      detail && typeof detail === "object" && "title" in detail
        ? String((detail as Record<string, unknown>).title)
        : typeof detail === "string"
          ? detail
          : fallback,
    );
    this.name = "ApprovalsApiError";
    this.status = status;
    this.detail = detail;
  }
}

// ---- Internals -------------------------------------------------------------

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
    throw new ApprovalsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

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

// ---- API object ------------------------------------------------------------

export const approvalsApi = {
  /**
   * Lista prices en `pending_review` con filtros opcionales.
   * Siempre fuerza status=pending_review para esta cola.
   */
  listQueue: (filters: ApprovalQueueFilters = {}): Promise<PriceListResponse> =>
    authedFetch<PriceListResponse>(
      `/api/v1/pricing/prices${buildQuery({
        status: "pending_review",
        channel: filters.channel,
        scheme: filters.scheme,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit ?? 50,
        include_total: true,
      })}`,
    ),

  /** Detalle de price con historial de eventos de aprobación. */
  getDetail: (id: string): Promise<PriceDetail> =>
    authedFetch<PriceDetail>(`/api/v1/pricing/prices/${id}`),

  /** Aprueba precio individual. */
  approve: (id: string, reason?: string): Promise<PriceRow> =>
    authedFetch<PriceRow>(`/api/v1/pricing/prices/${id}/approve`, {
      method: "POST",
      body: JSON.stringify({ reason: reason ?? null }),
    }),

  /** Rechaza precio individual. Razón obligatoria ≥10 chars (validado en UI). */
  reject: (id: string, reason: string): Promise<PriceRow> =>
    authedFetch<PriceRow>(`/api/v1/pricing/prices/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ reason }),
    }),

  /** Revisa precio (genera nueva propuesta con monto manual). */
  revise: (id: string, newAmount: string, reason: string): Promise<PriceRow> =>
    authedFetch<PriceRow>(`/api/v1/pricing/prices/${id}/revise`, {
      method: "POST",
      body: JSON.stringify({ new_amount: newAmount, reason }),
    }),

  /**
   * Bulk-approve.
   * Nota: backend usa `comment` (no `reason`) — campo obligatorio ≥10 chars.
   * Bulk > 50 items requiere comentario (validado también en UI).
   */
  bulkApprove: (
    price_ids: string[],
    comment: string,
  ): Promise<{ approved: number; failed: number; errors: string[] }> =>
    authedFetch(`/api/v1/pricing/prices/bulk-approve`, {
      method: "POST",
      body: JSON.stringify({ price_ids, comment }),
    }),
};
