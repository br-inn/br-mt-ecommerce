"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado mínimo para `/api/v1/certifications`.
 *
 * Stage 3 / Wave 11 sólo necesita READ para listar certificaciones en el
 * tab de "Series · Certificaciones". El CRUD admin completo lo maneja el
 * router `admin_vocab_router` (no usado aquí todavía).
 */

export interface Certification {
  id: string;
  code: string;
  name: string;
  issued_by: string | null;
  scope: string | null;
  logo_url: string | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export class CertificationsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "CertificationsApiError";
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
    throw new CertificationsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const certificationsApi = {
  /** Listado público (solo activas). */
  list: (): Promise<Certification[]> =>
    authedFetch<Certification[]>(`/api/v1/certifications`),
};
