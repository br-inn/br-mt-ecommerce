"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";
import type {
  AttributeDefinition,
  AttributeOption,
  AttributeValue,
  AttributeValueUpsertPayload,
  FamilyAttribute,
} from "@/lib/api/types-attributes";

/**
 * Typed wrappers for Fase 2 EAV attribute endpoints.
 *
 * Backend reference: `mt-pricing-backend/app/api/routes/attributes.py`.
 *
 * Note: the backend FamilyAttributeWithDefinition response carries
 * `attribute` (the joined AttributeDefinition); we normalise it to
 * `definition` on the client to match `FamilyAttribute.definition`.
 */

// ---------------------------------------------------------------------------
// Backend wire-shape (kept private)
// ---------------------------------------------------------------------------

interface BackendFamilyAttributeWithDefinition {
  id: string;
  family_id: string;
  attribute_id: string;
  group_code: string;
  order_index: number;
  is_required: boolean;
  default_value?: string | null;
  validation_rule?: Record<string, unknown> | null;
  attribute: AttributeDefinition;
}

// ---------------------------------------------------------------------------
// Auth + fetch helper (mirrors lib/api/endpoints/products.ts patterns)
// ---------------------------------------------------------------------------

export class AttributesApiError extends Error {
  public readonly status: number;
  public readonly detail: unknown;

  constructor(status: number, detail: unknown, fallback: string) {
    super(typeof detail === "string" ? detail : fallback);
    this.name = "AttributesApiError";
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
    throw new AttributesApiError(res.status, detail, res.statusText);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

// ---------------------------------------------------------------------------
// API
// ---------------------------------------------------------------------------

/**
 * `GET /api/v1/attributes` — list every attribute definition.
 */
export async function listAttributes(): Promise<AttributeDefinition[]> {
  return authedFetch<AttributeDefinition[]>(`/api/v1/attributes`);
}

/**
 * `GET /api/v1/attributes/{attr_id}/options` — list enum options.
 */
export async function listAttributeOptions(
  attrId: string,
): Promise<AttributeOption[]> {
  return authedFetch<AttributeOption[]>(`/api/v1/attributes/${attrId}/options`);
}

/**
 * `GET /api/v1/families/{family_id}/attributes` — list template attributes
 * for a family, with the joined AttributeDefinition eager-loaded.
 *
 * For enum-typed attributes the backend does NOT eager-load options; this
 * helper fetches them in parallel and attaches them to each returned
 * `FamilyAttribute.options`.
 */
export async function listFamilyAttributes(
  familyId: string,
): Promise<FamilyAttribute[]> {
  const raw = await authedFetch<BackendFamilyAttributeWithDefinition[]>(
    `/api/v1/families/${familyId}/attributes`,
  );

  // Fetch options in parallel for every enum-typed attribute.
  const enumRows = raw.filter((r) => r.attribute.data_type === "enum");
  const optionsByAttrId = new Map<string, AttributeOption[]>();
  await Promise.all(
    enumRows.map(async (r) => {
      try {
        const opts = await listAttributeOptions(r.attribute.id);
        optionsByAttrId.set(r.attribute.id, opts);
      } catch {
        // Non-fatal: leave options undefined so the UI can show "—".
      }
    }),
  );

  return raw.map<FamilyAttribute>((r) => ({
    id: r.id,
    family_id: r.family_id,
    attribute_id: r.attribute_id,
    group_code: r.group_code,
    order_index: r.order_index,
    is_required: r.is_required,
    default_value: r.default_value ?? null,
    validation_rule: r.validation_rule ?? null,
    definition: r.attribute,
    options: optionsByAttrId.get(r.attribute_id),
  }));
}

/**
 * `GET /api/v1/products/{sku}/attributes` — list attribute values for a
 * product.
 */
export async function listProductAttributeValues(
  sku: string,
): Promise<AttributeValue[]> {
  return authedFetch<AttributeValue[]>(`/api/v1/products/${sku}/attributes`);
}

/**
 * `PUT /api/v1/products/{sku}/attributes/{attr_code}` — upsert a value.
 */
export async function upsertProductAttributeValue(
  sku: string,
  attrCode: string,
  payload: AttributeValueUpsertPayload,
): Promise<AttributeValue> {
  return authedFetch<AttributeValue>(
    `/api/v1/products/${sku}/attributes/${attrCode}`,
    {
      method: "PUT",
      body: JSON.stringify(payload),
    },
  );
}

/**
 * `DELETE /api/v1/products/{sku}/attributes/{attr_code}` — remove a value.
 */
export async function deleteProductAttributeValue(
  sku: string,
  attrCode: string,
): Promise<void> {
  await authedFetch<void>(`/api/v1/products/${sku}/attributes/${attrCode}`, {
    method: "DELETE",
  });
}

export const attributesApi = {
  listAttributes,
  listAttributeOptions,
  listFamilyAttributes,
  listProductAttributeValues,
  upsertProductAttributeValue,
  deleteProductAttributeValue,
};
