"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/taxonomies/registry` y rutas asociadas.
 *
 * Data-driven sidebar + filters + form-builder. Reemplaza hardcoded
 * Divisiones/Series/Tiers/Materiales en el sidebar SISTEMA y prepara
 * el frontend para que nuevas taxonomías (mercados, certificaciones,
 * aplicaciones, etc.) aparezcan automáticamente sin código nuevo.
 *
 * Backend: mig 049/050 + app/api/routes/taxonomy_registry.py.
 */

export type TaxonomyValueKind =
  | "enum_closed"
  | "enum_open"
  | "numeric_with_unit"
  | "freetext"
  | "reference_to_other_type";

export interface TaxonomyTypeRead {
  id: string;
  slug: string;
  is_system: boolean;
  label_i18n: Record<string, string>;
  is_hierarchical: boolean;
  depth_max: number | null;
  value_kind: TaxonomyValueKind;
  filterable: boolean;
  display_order: number;
  ui_layout: {
    icon?: string;
    position?: number;
    custom_component?: string;
    groups?: string[];
  };
  governance_policy: Record<string, unknown>;
  required_for_products: boolean;
  external_mappings: Record<string, string>;
  schema_version: number;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface TaxonomyNodeRead {
  id: string;
  type_id: string;
  type_slug: string | null;
  slug: string;
  parent_id: string | null;
  labels: Record<string, string>;
  attributes: Record<string, unknown>;
  display_order: number;
  valid_from: string;
  valid_until: string | null;
  superseded_by: string | null;
  node_acl: Record<string, unknown> | null;
  active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProductTaxonomyLinkRead {
  product_sku: string;
  node_id: string;
  role: "belongs_to" | "compatible_with" | "replaces" | "recommends";
  weight: number;
  valid_from: string;
  valid_until: string | null;
  created_by: string | null;
  created_at: string;
}

export class TaxonomyRegistryApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;
  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "TaxonomyRegistryApiError";
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
    throw new TaxonomyRegistryApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export const taxonomyRegistryApi = {
  /** Listado de tipos del registry (drives sidebar SISTEMA y filtros). */
  listRegistry: (params?: {
    filterable_only?: boolean;
    include_inactive?: boolean;
  }): Promise<TaxonomyTypeRead[]> => {
    const query = new URLSearchParams();
    if (params?.filterable_only) query.set("filterable_only", "true");
    if (params?.include_inactive) query.set("include_inactive", "true");
    const qs = query.toString();
    return authedFetch<TaxonomyTypeRead[]>(
      `/api/v1/taxonomies/registry${qs ? `?${qs}` : ""}`,
    );
  },

  /** Metadatos de un tipo. */
  getType: (typeSlug: string): Promise<TaxonomyTypeRead> =>
    authedFetch<TaxonomyTypeRead>(
      `/api/v1/taxonomies/${encodeURIComponent(typeSlug)}`,
    ),

  /** Listar nodos (terms) de un tipo, ordenados por display_order. */
  listNodes: (
    typeSlug: string,
    params?: { include_inactive?: boolean; include_deprecated?: boolean },
  ): Promise<TaxonomyNodeRead[]> => {
    const query = new URLSearchParams();
    if (params?.include_inactive) query.set("include_inactive", "true");
    if (params?.include_deprecated) query.set("include_deprecated", "true");
    const qs = query.toString();
    return authedFetch<TaxonomyNodeRead[]>(
      `/api/v1/taxonomies/${encodeURIComponent(typeSlug)}/nodes${qs ? `?${qs}` : ""}`,
    );
  },

  /** Listar taxonomías linkeadas a un producto. */
  listForProduct: (
    sku: string,
    params?: { role?: string; type_slug?: string; include_historic?: boolean },
  ): Promise<ProductTaxonomyLinkRead[]> => {
    const query = new URLSearchParams();
    if (params?.role) query.set("role", params.role);
    if (params?.type_slug) query.set("type_slug", params.type_slug);
    if (params?.include_historic) query.set("include_historic", "true");
    const qs = query.toString();
    return authedFetch<ProductTaxonomyLinkRead[]>(
      `/api/v1/products/${encodeURIComponent(sku)}/taxonomies${qs ? `?${qs}` : ""}`,
    );
  },
};
