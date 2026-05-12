"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type { ProductCompatibility } from "@/lib/api/endpoints/products";

/**
 * Cliente tipado para el endpoint Fase 5
 * `GET /api/v1/series/{series_id}/spare-parts?dn={dn}`.
 *
 * Devuelve la lista de enlaces `product_compatibility` cuyos
 * `owner_type='series'` y cuyo rango `[dn_min, dn_max]` cubre el `dn` indicado
 * (NULL en cualquiera de los lados se interpreta como ilimitado).
 */

export class SparePartsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "SparePartsApiError";
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
    throw new SparePartsApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(params: Record<string, string | number | undefined | null>): string {
  const sp = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    sp.set(k, String(v));
  });
  const s = sp.toString();
  return s ? `?${s}` : "";
}

export const sparePartsApi = {
  /**
   * Lista los recambios (product_compatibility con owner_type='series')
   * aplicables a la serie indicada.
   *
   * @param seriesId — id (UUID) o code de la serie.
   * @param dn — opcional; si se pasa, sólo devuelve filas cuyo rango cubre el DN.
   */
  listSparePartsForSeries: (
    seriesId: string,
    dn?: number,
  ): Promise<ProductCompatibility[]> =>
    authedFetch<ProductCompatibility[]>(
      `/api/v1/series/${encodeURIComponent(seriesId)}/spare-parts${buildQuery({ dn })}`,
    ),
};
