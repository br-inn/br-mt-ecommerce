/**
 * Specs schema API — Wave 9 placeholder.
 *
 * Fetches the JSON Schema governing `products.specs` for a given family/subfamily
 * from `GET /api/v1/products/specs/schema`.
 *
 * Full UI integration ships in Wave 10 (dynamic form rendering per family).
 */

import { apiClient } from "@/lib/api/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * JSON Schema object as returned by the backend (Draft 2020-12).
 * Typed loosely — the exact shape varies per family.
 */
export interface SpecsSchema {
  $schema?: string;
  $id?: string;
  title?: string;
  description?: string;
  type: string;
  required?: string[];
  properties?: Record<string, SpecsSchemaProperty>;
  additionalProperties?: boolean | SpecsSchemaProperty;
}

export interface SpecsSchemaProperty {
  type?: string | string[];
  title?: string;
  description?: string;
  enum?: string[];
  minimum?: number;
  maximum?: number;
  exclusiveMinimum?: number;
  exclusiveMaximum?: number;
  minLength?: number;
  maxLength?: number;
  minItems?: number;
  maxItems?: number;
  items?: SpecsSchemaProperty;
  properties?: Record<string, SpecsSchemaProperty>;
  required?: string[];
  additionalProperties?: boolean | SpecsSchemaProperty;
  [key: string]: unknown;
}

// ---------------------------------------------------------------------------
// API calls
// ---------------------------------------------------------------------------

/**
 * Fetch the JSON Schema for `specs` JSONB of the given family/subfamily.
 *
 * Falls back to `_default` schema if no specific schema exists for the family.
 *
 * @param family - Product family key (e.g. "valve", "filter")
 * @param subfamily - Optional subfamily key (e.g. "ball")
 * @returns JSON Schema dict
 */
export async function getSpecsSchema(
  family: string,
  subfamily?: string
): Promise<SpecsSchema> {
  const params = new URLSearchParams({ family });
  if (subfamily) {
    params.set("subfamily", subfamily);
  }
  const response = await apiClient.get<SpecsSchema>(
    `/products/specs/schema?${params.toString()}`
  );
  return response.data;
}
