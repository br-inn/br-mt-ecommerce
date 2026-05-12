/**
 * Frontend types — Fase 2 EAV typed attributes.
 *
 * Mirrors `mt-pricing-backend/app/schemas/attributes.py` shapes.
 * Pure TS types — no runtime code.
 */

export type AttributeDataType =
  | "number"
  | "integer"
  | "text"
  | "bool"
  | "enum"
  | "range"
  | "dimension";

export type AttributeScope = "product" | "variant" | "both";

export type AttributeValueOwnerType = "product" | "variant";

export interface AttributeDefinition {
  id: string;
  code: string;
  label_en: string;
  data_type: AttributeDataType;
  unit?: string | null;
  description_en?: string | null;
  is_filterable: boolean;
  is_seo_relevant: boolean;
  scope: AttributeScope;
}

export interface AttributeOption {
  id: string;
  attribute_id: string;
  code: string;
  label_en: string;
  order_index: number;
}

export interface FamilyAttribute {
  id: string;
  family_id: string;
  attribute_id: string;
  group_code: string;
  order_index: number;
  is_required: boolean;
  default_value?: string | null;
  validation_rule?: Record<string, unknown> | null;
  /** Joined eager (returned by `GET /families/{id}/attributes`). */
  definition?: AttributeDefinition | undefined;
  options?: AttributeOption[] | undefined;
}

export interface AttributeValue {
  id: string;
  owner_type: AttributeValueOwnerType;
  owner_id: string;
  attribute_id: string;
  value_number?: number | null;
  value_text?: string | null;
  value_bool?: boolean | null;
  value_enum_id?: string | null;
  value_min?: number | null;
  value_max?: number | null;
  unit?: string | null;
  language?: string | null;
}

export interface AttributeValueUpsertPayload {
  value_number?: number | null;
  value_text?: string | null;
  value_bool?: boolean | null;
  value_enum_id?: string | null;
  value_min?: number | null;
  value_max?: number | null;
  unit?: string | null;
  language?: string | null;
}
