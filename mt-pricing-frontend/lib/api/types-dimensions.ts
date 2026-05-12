/**
 * Fase 3 — granular technical-table types.
 *
 * Mirror of the Pydantic V2 schemas exposed by the backend at
 * `mt-pricing-backend/app/schemas/dimensions.py`. Decimal fields arrive over
 * the wire as JSON numbers; the backend serialises Pydantic `Decimal` to
 * either string or number depending on FastAPI config. To be safe we accept
 * both forms here and the rendering layer is responsible for coercing.
 */

// ---------------------------------------------------------------------------
// Actuation codes (read-only catalogue)
// ---------------------------------------------------------------------------

export type ActuationType =
  | "free_shaft"
  | "handle"
  | "gearbox"
  | "motorized"
  | "pneumatic";

export interface ActuationCode {
  id: string;
  code: string;
  name_en: string;
  type: ActuationType;
  created_at?: string;
}

// ---------------------------------------------------------------------------
// Standards
// ---------------------------------------------------------------------------

export interface Standard {
  id: string;
  code: string;
  edition: string;
  title_en: string;
  reference_url: string | null;
  created_at?: string;
}

// ---------------------------------------------------------------------------
// Dimension table — column / row / cell
// ---------------------------------------------------------------------------

export interface DimensionColumn {
  id: string;
  family_id: string;
  code: string;
  label_en: string;
  unit: string | null;
  order_index: number;
}

export interface DimensionCell {
  id: string;
  row_id: string;
  column_id: string;
  /**
   * Pydantic `Decimal` may serialise as either string or number depending on
   * backend config. Renderers must coerce with `Number()`.
   */
  value_number: number | string | null;
  value_text: string | null;
}

export interface DimensionRow {
  id: string;
  product_sku: string;
  size_label: string | null;
  dn: number | null;
  actuation_code_id: string | null;
  order_index: number;
  created_at?: string;
}

export interface DimensionRowWithCells extends DimensionRow {
  cells: DimensionCell[];
}

export interface DimensionTableResponse {
  product_sku: string;
  family_id: string | null;
  columns: DimensionColumn[];
  rows: DimensionRowWithCells[];
}

// ---------------------------------------------------------------------------
// Pressure-Temperature curve
// ---------------------------------------------------------------------------

export interface PressureTemperaturePoint {
  id: string;
  product_sku: string;
  series_variant_code: string | null;
  temperature_c: number | string;
  pressure_max_bar: number | string;
  condition_en: string | null;
  order_index: number;
  created_at?: string;
}

/**
 * Backend returns a single bucket per call (filtered by `series_variant_code`),
 * but the FE composite chart aggregates points across buckets when the
 * `series_variant_code` query param is omitted. We therefore type the curve
 * loosely so the consumer can group client-side.
 */
export interface PressureTemperatureCurveResponse {
  product_sku: string;
  series_variant_code: string | null;
  points: PressureTemperaturePoint[];
}
