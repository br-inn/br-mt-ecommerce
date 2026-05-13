"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/admin/erp-eventos/*` (US-INV-01-07).
 *
 * Expone el log de eventos ERP salientes (outbox) con filtros por estado
 * y acción de reintento para filas `failed`.
 */

// ---- Types ------------------------------------------------------------------

export type ERPSyncStatus = "pending" | "delivered" | "failed" | "skipped";

export interface ERPSyncEvent {
  id: string;
  event_type: string;
  entity_id: string | null;
  adapter: string;
  status: ERPSyncStatus;
  attempts: number;
  last_error: string | null;
  external_ref: string | null;
  delivered_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface ERPSyncEventsPage {
  items: ERPSyncEvent[];
  next_cursor: string | null;
}

// ---- Helpers ----------------------------------------------------------------

async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ---- API calls --------------------------------------------------------------

/**
 * Lista ERPSyncEvents con filtro opcional por estado y cursor pagination.
 */
export async function listErpEventos(params?: {
  status?: ERPSyncStatus;
  limit?: number;
  cursor?: string;
}): Promise<ERPSyncEventsPage> {
  const headers = await getAuthHeaders();
  const url = new URL(`${env.NEXT_PUBLIC_API_URL}/api/v1/admin/erp-eventos`);

  if (params?.status) url.searchParams.set("status", params.status);
  if (params?.limit) url.searchParams.set("limit", String(params.limit));
  if (params?.cursor) url.searchParams.set("cursor", params.cursor);

  const res = await fetch(url.toString(), { headers });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`listErpEventos ${res.status}: ${body}`);
  }
  return res.json() as Promise<ERPSyncEventsPage>;
}

/**
 * Resetea un evento `failed` a `pending` y re-encola la task.
 */
export async function retryErpEvento(eventId: string): Promise<ERPSyncEvent> {
  const headers = await getAuthHeaders();
  const res = await fetch(
    `${env.NEXT_PUBLIC_API_URL}/api/v1/admin/erp-eventos/${eventId}/retry`,
    {
      method: "PATCH",
      headers,
    }
  );
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`retryErpEvento ${res.status}: ${body}`);
  }
  return res.json() as Promise<ERPSyncEvent>;
}
