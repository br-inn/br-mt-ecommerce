"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Wrappers tipados para `/api/v1/audit/*`.
 *
 * Sprint 1.5 (US-1A-07-01): el endpoint expone una timeline filtrable de
 * audit_events para producto/usuario/job/role. Cursor opaco base64url-JSON.
 */

export interface AuditActorRef {
  id: string | null;
  email: string | null;
  full_name: string | null;
}

export interface AuditEvent {
  /** BigInt serializado como string — opaque ID para el cliente. */
  id: string;
  event_at: string;
  actor: AuditActorRef | null;
  entity_type: string;
  entity_id: string;
  action: string;
  before: Record<string, unknown> | null;
  after: Record<string, unknown> | null;
  payload_diff: Record<string, unknown>;
  reason: string | null;
  request_id: string | null;
  current_hash: string | null;
  prev_hash: string | null;
}

export interface AuditEventsPage {
  items: AuditEvent[];
  cursor: { next: string | null; prev?: string | null };
  page_size: number;
  total?: number | null;
}

export interface AuditEventFilters {
  entity_type?: string | undefined;
  entity_id?: string | undefined;
  actor_id?: string | undefined;
  action?: string | undefined;
  since?: string | undefined;
  until?: string | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
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
    throw new Error(
      typeof detail === "object" && detail && "detail" in detail
        ? JSON.stringify((detail as { detail: unknown }).detail)
        : res.statusText,
    );
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

export const auditApi = {
  listEvents: (filters: AuditEventFilters): Promise<AuditEventsPage> =>
    authedFetch<AuditEventsPage>(
      `/api/v1/audit/events${buildQuery({
        entity_type: filters.entity_type,
        entity_id: filters.entity_id,
        actor_id: filters.actor_id,
        action: filters.action,
        since: filters.since,
        until: filters.until,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
      })}`,
    ),
};
