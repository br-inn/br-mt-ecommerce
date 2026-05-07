"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type {
  AuditEvent,
  AuditEventsPage,
} from "@/lib/api/endpoints/audit";

/**
 * Wrapper extendido para `/api/v1/audit-events` (Sprint 4 — Agente A).
 *
 * Vs `audit.ts` (S1.5): permite multi-entity_type (CSV) + filtros adicionales
 * (action, since/until, actor email/id). Compatible con el shape `AuditEvent`
 * existente. Convive con `auditApi.listEvents` hasta que el backend S4
 * consolide ambos.
 */

export interface AuditQueryFilters {
  /** CSV: `products,costs,prices` etc. */
  entity_types?: string[] | undefined;
  entity_id?: string | undefined;
  actor_id?: string | undefined;
  actor_email?: string | undefined;
  action?: string | undefined;
  /** ISO date string. */
  from?: string | undefined;
  to?: string | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
}

export class AuditQueryApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "AuditQueryApiError";
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
    throw new AuditQueryApiError(res.status, detail, res.statusText);
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

export const auditQueryApi = {
  /**
   * Lista audit-events con filtros multi-entidad. El backend acepta
   * `entity_type` como CSV (e.g. `products,costs,prices`).
   */
  listEvents: (filters: AuditQueryFilters): Promise<AuditEventsPage> => {
    const entityTypes = filters.entity_types?.length
      ? filters.entity_types.join(",")
      : undefined;
    return authedFetch<AuditEventsPage>(
      `/api/v1/audit-events${buildQuery({
        entity_type: entityTypes,
        entity_id: filters.entity_id,
        actor_id: filters.actor_id,
        actor_email: filters.actor_email,
        action: filters.action,
        from: filters.from,
        to: filters.to,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
      })}`,
    );
  },
};

export type { AuditEvent, AuditEventsPage };
