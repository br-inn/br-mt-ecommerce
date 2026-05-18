"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/schemes` (US-1A-04-S4).
 *
 * Endpoints:
 *  - GET /api/v1/schemes           — lista todos los schemes activos.
 *  - GET /api/v1/schemes/{code}    — scheme concreto por código.
 *
 * Los schemes son datos de configuración semestática (no cambian en
 * producción). El hook usa staleTime de 1 hora.
 */

// ---- Types ----------------------------------------------------------------

export interface CostComponentsTemplate {
  required: string[];
  optional: string[];
}

export interface Scheme {
  code: string;
  name: string;
  description: string | null;
  cost_components_template: CostComponentsTemplate;
  active: boolean;
}

// ---- Internals ------------------------------------------------------------

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
    throw new Error(`schemes API error ${res.status}: ${res.statusText}`);
  }
  return (await res.json()) as T;
}

// ---- API ------------------------------------------------------------------

export const schemesApi = {
  /** GET /schemes — lista todos los schemes activos. */
  list: (): Promise<Scheme[]> =>
    authedFetch<Scheme[]>("/api/v1/schemes"),

  /** GET /schemes/{code} — scheme individual (e.g. "FBA"). */
  get: (code: string): Promise<Scheme> =>
    authedFetch<Scheme>(`/api/v1/schemes/${encodeURIComponent(code)}`),
};
