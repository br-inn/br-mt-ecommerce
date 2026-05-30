"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

/**
 * Cliente tipado para `/api/v1/costs` — contrato de vigencia por rangos.
 *
 * Endpoints:
 *  - GET    /api/v1/costs?sku=&scheme=&supplier=&valid_on=&include_history=&cursor=&limit=&include_total=
 *  - GET    /api/v1/costs/as-of?sku=&scheme_code=&supplier_code=&date=
 *  - GET    /api/v1/costs/missing?scheme_code=&as_of=
 *  - POST   /api/v1/costs                        body { ..., valid_from }
 *  - GET    /api/v1/costs/{id}
 *  - PUT    /api/v1/costs/{id}                    corrección in-place
 *  - PATCH  /api/v1/costs/{id}                    corrección in-place (legacy)
 *  - POST   /api/v1/costs/{id}/close             body { valid_to }
 *  - DELETE /api/v1/costs/{id}
 *  - GET    /api/v1/products/{sku}/costs?as_of=
 *
 * El backend devuelve { items, cursor: { next }, page_size, total }.
 *
 * Contrato de vigencia: `Cost` expone los rangos reales `valid_from`/`valid_to`
 * (fecha "YYYY-MM-DD"). `status` ("active"/"superseded") sigue presente como
 * campo derivado. Los payloads de REQUEST usan `valid_from` (no `effective_at`):
 * el schema del backend es `extra="forbid"`.
 */

export interface CostBreakdown {
  fob?: number | string | null;
  freight?: number | string | null;
  customs?: number | string | null;
  fba_fee?: number | string | null;
  fbm_fee?: number | string | null;
  payment_fee?: number | string | null;
  marketing?: number | string | null;
  storage?: number | string | null;
  ppc?: number | string | null;
  otros?: number | string | null;
  [k: string]: number | string | null | undefined;
}

export interface Cost {
  id: string;
  // ── Canonical (US-1A-04-02) ───────────────────────────────────────
  sku: string;
  scheme_code: string;
  supplier_code: string | null;
  currency_origin: string;
  fx_rate_id: string | null;
  breakdown: CostBreakdown;
  scheme_landed_aed: string | null;
  // ── Vigencia por rangos (campos reales) ───────────────────────────
  valid_from: string; // date "YYYY-MM-DD"
  valid_to: string | null; // date "YYYY-MM-DD" | null (abierto)
  status: "active" | "superseded"; // derivado (híbrido) — sigue presente
  fx_inferred: boolean;
  version: number;
  created_by: string | null;
  updated_by: string | null;
  created_at: string;
  updated_at: string;
  // ── Compat read-only (el backend aún las devuelve) ────────────────
  // `effective_at` es un alias híbrido (== valid_from a medianoche); se
  // mantiene como opcional de sólo lectura hasta que Task 2 migre a
  // `valid_from` los consumidores que aún lo leen.
  effective_at?: string;
  product_sku?: string;
  total?: string | null;
  currency?: string;
  fx_at?: string | null;
}

export interface CostWarning {
  code: string; // e.g. "unknown_breakdown_field"
  field: string;
}

/** Response del POST/PUT NUEVO motor (US-1A-04-03). */
export interface CostCreatedResponse {
  cost: Cost;
  warnings: CostWarning[];
}

export interface CostMissingItem {
  sku: string;
  name: string | null;
}

export interface CostsListResponse {
  items: Cost[];
  cursor: { next: string | null; prev: string | null };
  page_size: number;
  total: number | null;
}

/**
 * Payload para POST /costs (contrato de vigencia por rangos).
 * - `sku` (canonical) en lugar de `product_sku`.
 * - `currency_origin` en lugar de `currency`.
 * - `valid_from` (fecha "YYYY-MM-DD") — inicio de vigencia. El backend cierra
 *   automáticamente la fila abierta previa.
 * - Sin `total` — el backend lo calcula vía trigger.
 *
 * `effective_at` está DEPRECADO: el schema del backend es `extra="forbid"`, así
 * que `costsApi.create` nunca lo envía. Se mantiene como opcional sólo para no
 * romper consumidores que aún lo construyen (Task 2 los migra); si `valid_from`
 * está ausente, `costsApi.create` lo deriva de `effective_at` (parte fecha).
 */
export interface CostCreatePayload {
  sku: string;
  scheme_code: string;
  supplier_code?: string | null | undefined;
  currency_origin: string;
  valid_from?: string | undefined; // date "YYYY-MM-DD"
  /** @deprecated usar `valid_from`. No se envía al backend. */
  effective_at?: string | undefined;
  breakdown: CostBreakdown;
  fx_rate_id?: string | null | undefined;
  fx_inferred?: boolean | undefined;
}

/**
 * Payload del PUT/PATCH — corrección IN-PLACE (no versiona, no toca `valid_to`).
 * Para cerrar un rango usar `costsApi.close`.
 */
export interface CostUpdatePayload {
  breakdown?: CostBreakdown | undefined;
  valid_from?: string | undefined; // date "YYYY-MM-DD"
  /** @deprecated usar `valid_from`. No se envía al backend. */
  effective_at?: string | undefined;
  currency_origin?: string | undefined;
  fx_rate_id?: string | null | undefined;
  fx_inferred?: boolean | undefined;
}

/** Legacy — usado por el endpoint PATCH deprecated. */
export interface LegacyCostCreatePayload {
  product_sku: string;
  scheme_code: string;
  supplier_code?: string | null | undefined;
  breakdown: CostBreakdown;
  total: number | string;
  currency: string;
  valid_from?: string | null | undefined;
  valid_to?: string | null | undefined;
}

export interface CostPatchPayload {
  scheme_code?: string | undefined;
  supplier_code?: string | null | undefined;
  breakdown?: CostBreakdown | undefined;
  total?: number | string | undefined;
  currency?: string | undefined;
  valid_from?: string | null | undefined;
  valid_to?: string | null | undefined;
}

export interface CostFilters {
  /** Filtro por SKU (param canónico `sku`; backend acepta también `product_sku`). */
  sku?: string | undefined;
  product_sku?: string | undefined;
  scheme?: string | undefined;
  supplier?: string | undefined;
  /** Fecha "YYYY-MM-DD": sólo costos cuyo rango contiene la fecha. */
  valid_on?: string | undefined;
  /** `true` devuelve todos los rangos (historia); default sólo vigentes hoy. */
  include_history?: boolean | undefined;
  cursor?: string | null | undefined;
  limit?: number | undefined;
  include_total?: boolean | undefined;
}

// Esquemas válidos (alineado con backend enum).
export const COST_SCHEMES = [
  "FBA",
  "FBM",
  "DIRECT_B2C",
  "DIRECT_B2B",
  "MARKETPLACE",
] as const;
export type CostScheme = (typeof COST_SCHEMES)[number];

// ---- Errors ---------------------------------------------------------------

export class CostsApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "CostsApiError";
    this.status = status;
    this.detail = detail;
  }

  /**
   * Código de dominio del error. El backend devuelve `{"detail": {"code": ...}}`
   * (p.ej. `cost_range_overlap`, `cost_not_found`, `fx_rate_not_found_at_effective_at`).
   * Devuelve `null` si el cuerpo no trae un `detail.code` string.
   */
  public code(): string | null {
    const detail = this.detail;
    if (!detail || typeof detail !== "object") return null;
    const inner = (detail as { detail?: unknown }).detail;
    if (inner && typeof inner === "object") {
      const c = (inner as { code?: unknown }).code;
      if (typeof c === "string") return c;
    }
    // Algunos errores ponen el code en la raíz.
    const rootCode = (detail as { code?: unknown }).code;
    return typeof rootCode === "string" ? rootCode : null;
  }

  public fieldErrors(): Record<string, string> | null {
    const detail = this.detail;
    if (!detail || typeof detail !== "object") return null;
    const inner = (detail as { detail?: unknown }).detail;

    // Forma nueva: detail es un objeto { code, title, field? }.
    if (inner && typeof inner === "object" && !Array.isArray(inner)) {
      const field = (inner as { field?: unknown }).field;
      const code = (inner as { code?: unknown }).code;
      const title = (inner as { title?: unknown }).title;
      if (typeof field === "string" && field) {
        const msg =
          typeof title === "string"
            ? title
            : typeof code === "string"
              ? code
              : "invalid";
        return { [field]: msg };
      }
      return null;
    }

    // Forma FastAPI 422: detail es un array de { loc, msg }.
    if (!Array.isArray(inner)) return null;
    const out: Record<string, string> = {};
    for (const it of inner) {
      if (!it || typeof it !== "object") continue;
      const loc = (it as { loc?: unknown }).loc;
      const msg = (it as { msg?: unknown }).msg;
      if (Array.isArray(loc) && typeof msg === "string") {
        const key = loc.filter((p) => p !== "body").join(".");
        if (key) out[key] = msg;
      }
    }
    return Object.keys(out).length > 0 ? out : null;
  }
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
    let detail: unknown;
    try {
      detail = await res.json();
    } catch {
      /* noop */
    }
    throw new CostsApiError(res.status, detail, res.statusText);
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

/**
 * Deriva `valid_from` (fecha "YYYY-MM-DD") del payload.
 * Prefiere `valid_from`; si sólo viene `effective_at` (deprecado, p.ej. un
 * datetime ISO), toma la parte fecha. El backend es `extra="forbid"`, así que
 * `effective_at` NUNCA se envía en el body.
 */
function resolveValidFrom(
  payload: { valid_from?: string | undefined; effective_at?: string | undefined },
): string | undefined {
  if (payload.valid_from) return payload.valid_from;
  if (payload.effective_at) return payload.effective_at.slice(0, 10);
  return undefined;
}

// ---- API ------------------------------------------------------------------

export const costsApi = {
  list: (filters: CostFilters = {}): Promise<CostsListResponse> =>
    authedFetch<CostsListResponse>(
      `/api/v1/costs${buildQuery({
        sku: filters.sku ?? filters.product_sku,
        scheme: filters.scheme,
        supplier: filters.supplier,
        valid_on: filters.valid_on,
        include_history: filters.include_history,
        cursor: filters.cursor ?? undefined,
        limit: filters.limit,
        include_total: filters.include_total,
      })}`,
    ),
  get: (id: string): Promise<Cost> =>
    authedFetch<Cost>(`/api/v1/costs/${encodeURIComponent(id)}`),
  /**
   * GET /costs/as-of — coste vigente a una fecha para sku+scheme(+supplier).
   * 404 (CostsApiError, code `cost_not_found`) si no hay coste vigente.
   */
  asOf: (params: {
    sku: string;
    scheme_code: string;
    supplier_code?: string | null | undefined;
    date: string;
  }): Promise<Cost> =>
    authedFetch<Cost>(
      `/api/v1/costs/as-of${buildQuery({
        sku: params.sku,
        scheme_code: params.scheme_code,
        supplier_code: params.supplier_code ?? undefined,
        date: params.date,
      })}`,
    ),
  /** POST nuevo motor — devuelve { cost, warnings }. Envía `valid_from`. */
  create: (payload: CostCreatePayload): Promise<CostCreatedResponse> => {
    const { effective_at: _ignored, ...rest } = payload;
    const body = { ...rest, valid_from: resolveValidFrom(payload) };
    return authedFetch<CostCreatedResponse>(`/api/v1/costs`, {
      method: "POST",
      body: JSON.stringify(body),
    });
  },
  /** PUT corrección in-place — devuelve { cost, warnings }. Envía `valid_from`. */
  update: (
    id: string,
    payload: CostUpdatePayload,
  ): Promise<CostCreatedResponse> => {
    const { effective_at: _ignored, ...rest } = payload;
    const validFrom = resolveValidFrom(payload);
    const body =
      validFrom !== undefined ? { ...rest, valid_from: validFrom } : rest;
    return authedFetch<CostCreatedResponse>(
      `/api/v1/costs/${encodeURIComponent(id)}`,
      {
        method: "PUT",
        body: JSON.stringify(body),
      },
    );
  },
  patch: (id: string, payload: CostPatchPayload): Promise<Cost> =>
    authedFetch<Cost>(`/api/v1/costs/${encodeURIComponent(id)}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  /** POST /costs/{id}/close — fija `valid_to` (descatalogar / cierre sin sucesor). */
  close: (id: string, valid_to: string): Promise<Cost> =>
    authedFetch<Cost>(`/api/v1/costs/${encodeURIComponent(id)}/close`, {
      method: "POST",
      body: JSON.stringify({ valid_to }),
    }),
  delete: (id: string): Promise<void> =>
    authedFetch<void>(`/api/v1/costs/${encodeURIComponent(id)}`, {
      method: "DELETE",
    }),
  /** GET /products/{sku}/costs — costes vigentes del SKU (opcional `as_of`). */
  listForSku: (
    sku: string,
    asOf?: string,
    onlyActive = true,
  ): Promise<Cost[]> =>
    authedFetch<Cost[]>(
      `/api/v1/products/${encodeURIComponent(sku)}/costs${buildQuery({
        only_active: onlyActive,
        as_of: asOf,
      })}`,
    ),
  /** GET /costs/missing — SKUs sin coste vigente para un scheme (opcional `as_of`). */
  missingForScheme: (
    schemeCode: string,
    asOf?: string,
    limit = 1000,
  ): Promise<CostMissingItem[]> =>
    authedFetch<CostMissingItem[]>(
      `/api/v1/costs/missing${buildQuery({
        scheme_code: schemeCode,
        as_of: asOf,
        limit,
      })}`,
    ),
};
