"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/series` y `/api/v1/admin/series`
 * (Stage 3 / Wave 11).
 *
 * Cubre:
 *  - CRUD básico de Series.
 *  - Sub-recurso de traducciones (`PUT /admin/series/{id}/translations/{lang}`,
 *    `DELETE` ídem).
 *  - Junction divisions (`POST/DELETE /admin/series/{id}/divisions/{div_id}`).
 *  - Junction certifications (`POST/DELETE /admin/series/{id}/certifications/{cert_id}`).
 */

export type SeriesLang = "es" | "ar" | "en";

export interface Series {
  id: string;
  code: string;
  name_en: string;
  tier_id: string | null;
  pressure_rating_pn: number | null;
  temperature_min_c: number | null;
  temperature_max_c: number | null;
  banner_color: string | null;
  hero_image_url: string | null;
  description_en: string | null;
  bullets_en: string[];
  features_tags: string[];
  sort_order: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface SeriesCreatePayload {
  code: string;
  name_en: string;
  tier_id?: string | null;
  pressure_rating_pn?: number | null;
  temperature_min_c?: number | null;
  temperature_max_c?: number | null;
  banner_color?: string | null;
  hero_image_url?: string | null;
  description_en?: string | null;
  bullets_en?: string[];
  features_tags?: string[];
  sort_order?: number;
  active?: boolean;
}

export interface SeriesPatchPayload {
  name_en?: string | null;
  tier_id?: string | null;
  pressure_rating_pn?: number | null;
  temperature_min_c?: number | null;
  temperature_max_c?: number | null;
  banner_color?: string | null;
  hero_image_url?: string | null;
  description_en?: string | null;
  bullets_en?: string[] | null;
  features_tags?: string[] | null;
  sort_order?: number | null;
  active?: boolean | null;
}

export interface SeriesTranslation {
  series_id: string;
  lang: SeriesLang;
  name: string;
  description: string | null;
  bullets: string[];
  created_at: string;
  updated_at: string;
}

export interface SeriesTranslationUpsertPayload {
  lang: SeriesLang;
  name: string;
  description?: string | null;
  bullets?: string[];
}

export class SeriesApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "SeriesApiError";
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
    throw new SeriesApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

function buildQuery(params: Record<string, string | undefined>): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === "") return;
    search.set(k, v);
  });
  const s = search.toString();
  return s ? `?${s}` : "";
}

export const seriesApi = {
  // Public
  listPublic: (filters: { division_id?: string } = {}): Promise<Series[]> =>
    authedFetch<Series[]>(
      `/api/v1/series${buildQuery({ division_id: filters.division_id })}`,
    ),
  getPublic: (id: string): Promise<Series> =>
    authedFetch<Series>(`/api/v1/series/${id}`),
  listTranslationsPublic: (id: string): Promise<SeriesTranslation[]> =>
    authedFetch<SeriesTranslation[]>(`/api/v1/series/${id}/translations`),

  // Admin CRUD
  list: (): Promise<Series[]> =>
    authedFetch<Series[]>(`/api/v1/admin/series`),
  create: (payload: SeriesCreatePayload): Promise<Series> =>
    authedFetch<Series>(`/api/v1/admin/series`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  patch: (id: string, payload: SeriesPatchPayload): Promise<Series> =>
    authedFetch<Series>(`/api/v1/admin/series/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  remove: (id: string): Promise<void> =>
    authedFetch<void>(`/api/v1/admin/series/${id}`, { method: "DELETE" }),

  // Translations
  upsertTranslation: (
    id: string,
    lang: SeriesLang,
    payload: SeriesTranslationUpsertPayload,
  ): Promise<SeriesTranslation> =>
    authedFetch<SeriesTranslation>(
      `/api/v1/admin/series/${id}/translations/${lang}`,
      {
        method: "PUT",
        body: JSON.stringify(payload),
      },
    ),
  deleteTranslation: (id: string, lang: SeriesLang): Promise<void> =>
    authedFetch<void>(`/api/v1/admin/series/${id}/translations/${lang}`, {
      method: "DELETE",
    }),

  // Junction: divisions
  linkDivision: (id: string, divisionId: string): Promise<void> =>
    authedFetch<void>(
      `/api/v1/admin/series/${id}/divisions/${divisionId}`,
      { method: "POST" },
    ),
  unlinkDivision: (id: string, divisionId: string): Promise<void> =>
    authedFetch<void>(
      `/api/v1/admin/series/${id}/divisions/${divisionId}`,
      { method: "DELETE" },
    ),

  // Junction: certifications
  linkCertification: (id: string, certificationId: string): Promise<void> =>
    authedFetch<void>(
      `/api/v1/admin/series/${id}/certifications/${certificationId}`,
      { method: "POST" },
    ),
  unlinkCertification: (id: string, certificationId: string): Promise<void> =>
    authedFetch<void>(
      `/api/v1/admin/series/${id}/certifications/${certificationId}`,
      { method: "DELETE" },
    ),
};
