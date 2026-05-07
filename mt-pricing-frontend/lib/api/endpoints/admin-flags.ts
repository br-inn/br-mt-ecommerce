"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/admin/flags` (US-1A-DEV-01 frontend / S5).
 *
 * Endpoints (Agente C S5):
 *  - GET    /api/v1/admin/flags
 *  - PATCH  /api/v1/admin/flags/{key}            { value, reason? }
 *  - POST   /api/v1/admin/flags/kill-switch      { reason }   (todo-OFF)
 */

export type FlagValueType = "bool" | "int" | "string";

export interface AdminFlag {
  key: string;
  value: boolean | number | string;
  value_type: FlagValueType;
  description: string | null;
  category: string | null;
  is_kill_switch: boolean;
  updated_at: string;
  updated_by: string | null;
}

export interface AdminFlagPatchPayload {
  value: boolean | number | string;
  reason?: string | null | undefined;
}

export interface AdminKillSwitchPayload {
  reason: string;
}

export interface AdminKillSwitchResponse {
  triggered_at: string;
  flags_disabled: string[];
  triggered_by: string | null;
}

export class AdminFlagsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "AdminFlagsApiError";
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
    throw new AdminFlagsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const adminFlagsApi = {
  list: (): Promise<AdminFlag[]> => authedFetch<AdminFlag[]>(`/api/v1/admin/flags`),
  patch: (key: string, payload: AdminFlagPatchPayload): Promise<AdminFlag> =>
    authedFetch<AdminFlag>(`/api/v1/admin/flags/${encodeURIComponent(key)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  killSwitch: (payload: AdminKillSwitchPayload): Promise<AdminKillSwitchResponse> =>
    authedFetch<AdminKillSwitchResponse>(`/api/v1/admin/flags/kill-switch`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
};
