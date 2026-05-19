"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// ---------------------------------------------------------------------------
// Types — EP-INV-01
// ---------------------------------------------------------------------------

export interface InventoryPositionRead {
  id: string;
  sku: string;
  supplier_code: string;
  scheme_code: string;
  qty_on_hand: string;
  map_aed: string | null;
  total_stock_value_aed: string | null;
  last_gr_id: string | null;
  last_updated_at: string | null;
  warehouse_id: string | null;
  lot_id: string | null;
  location_id: string | null;
  stock_type: string;
  product_name: string | null;
}

export interface MAPHistoryPoint {
  gr_id: string;
  map_before: string | null;
  map_after: string;
  qty_received: string;
  received_at: string;
  po_number: string;
}

export interface InventorySummary {
  total_skus_with_stock: number;
  total_stock_value_aed: string;
  skus_without_cost: number;
  pending_gr_count: number;
}

export interface InventoryPositionFilters {
  sku?: string;
  supplier_code?: string;
  scheme_code?: string;
  has_stock?: boolean;
  stock_type?: string;
  warehouse_id?: string;
  zone_id?: string;
}

// ---------------------------------------------------------------------------
// Types — US-ERP-02-01: Movement Types + Movements
// ---------------------------------------------------------------------------

export interface StockMovementTypeRead {
  id: string;
  code: string;
  name: string;
  direction: "IN" | "OUT" | "TRANSFER";
  requires_reference: boolean;
  posts_accounting: boolean;
  is_active: boolean;
}

export interface JournalEntryRead {
  id: string;
  source_movement_id: string;
  debit_account: string;
  credit_account: string;
  amount: string;
  currency: string;
  posted_at: string;
}

export interface StockMovementRead {
  id: string;
  movement_type_id: string;
  product_sku: string;
  qty: string;
  lot_id: string | null;
  warehouse_id: string | null;
  location_id: string | null;
  reference_id: string | null;
  reference_type: string | null;
  reversal_of: string | null;
  posted_at: string;
  posted_by: string | null;
  notes: string | null;
  journal_entries: JournalEntryRead[];
}

export interface StockMovementCreate {
  movement_type_id: string;
  product_sku: string;
  qty: number;
  lot_id?: string;
  warehouse_id?: string;
  location_id?: string;
  reference_id?: string;
  reference_type?: string;
  notes?: string;
}

// ---------------------------------------------------------------------------
// Types — US-ERP-02-03: Lot tracking
// ---------------------------------------------------------------------------

export interface InventoryLotRead {
  id: string;
  lot_number: string;
  product_sku: string;
  manufacture_date: string | null;
  expiry_date: string | null;
  country_of_origin: string | null;
  quality_status: string;
  po_line_id: string | null;
  created_at: string;
}

export interface LotTraceabilityRead {
  lot: InventoryLotRead;
  upstream: {
    lot_id: string;
    lot_number: string;
    po_line_id: string | null;
    po_number: string | null;
    supplier_code: string | null;
  };
  downstream: Array<{
    movement_id: string;
    movement_type_code: string;
    qty: string;
    reference_id: string | null;
    reference_type: string | null;
    posted_at: string;
  }>;
}

// ---------------------------------------------------------------------------
// Types — US-ERP-02-04: Warehouses
// ---------------------------------------------------------------------------

export interface WarehouseRead {
  id: string;
  code: string;
  name: string;
  address: string | null;
  is_active: boolean;
}

export interface WarehouseCreate {
  code: string;
  name: string;
  address?: string;
}

export interface WarehouseZoneRead {
  id: string;
  warehouse_id: string;
  code: string;
  name: string;
  zone_type: string | null;
}

export interface WarehouseZoneCreate {
  code: string;
  name: string;
  zone_type?: string;
}

export interface WarehouseLocationRead {
  id: string;
  zone_id: string;
  bin_code: string;
  is_active: boolean;
  max_weight: string | null;
}

// ---------------------------------------------------------------------------
// Error class
// ---------------------------------------------------------------------------

export class InventoryApiError extends Error {
  constructor(
    public readonly statusCode: number,
    public readonly detail: unknown,
    message?: string,
  ) {
    super(message ?? `Inventory API error ${statusCode}`);
    this.name = "InventoryApiError";
  }
}

// ---------------------------------------------------------------------------
// Authenticated fetch helper
// ---------------------------------------------------------------------------

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
    throw new InventoryApiError(res.status, detail, res.statusText);
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

// ---------------------------------------------------------------------------
// API — Inventory
// ---------------------------------------------------------------------------

const BASE = "/api/v1/inventory";
const WH_BASE = "/api/v1/warehouses";

export const inventoryApi = {
  listPositions: (
    filters: InventoryPositionFilters = {},
  ): Promise<InventoryPositionRead[]> =>
    authedFetch<InventoryPositionRead[]>(
      `${BASE}/positions${buildQuery({
        sku: filters.sku,
        supplier_code: filters.supplier_code,
        scheme_code: filters.scheme_code,
        has_stock: filters.has_stock,
        stock_type: filters.stock_type,
        warehouse_id: filters.warehouse_id,
        zone_id: filters.zone_id,
      })}`,
    ),

  getPositionsBySku: (sku: string): Promise<InventoryPositionRead[]> =>
    authedFetch<InventoryPositionRead[]>(`${BASE}/positions/${encodeURIComponent(sku)}`),

  getMAPHistory: (sku: string, limit = 50): Promise<MAPHistoryPoint[]> =>
    authedFetch<MAPHistoryPoint[]>(
      `${BASE}/positions/${encodeURIComponent(sku)}/map-history${buildQuery({ limit })}`,
    ),

  getSummary: (): Promise<InventorySummary> =>
    authedFetch<InventorySummary>(`${BASE}/summary`),

  // US-ERP-02-01: Movement Types + Movements
  listMovementTypes: (): Promise<StockMovementTypeRead[]> =>
    authedFetch<StockMovementTypeRead[]>(`${BASE}/movement-types`),

  listMovements: (limit = 50): Promise<StockMovementRead[]> =>
    authedFetch<StockMovementRead[]>(`${BASE}/movements${buildQuery({ limit })}`),

  createMovement: (payload: StockMovementCreate): Promise<StockMovementRead> =>
    authedFetch<StockMovementRead>(`${BASE}/movements`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  reverseMovement: (movementId: string): Promise<StockMovementRead> =>
    authedFetch<StockMovementRead>(`${BASE}/movements/${movementId}/reverse`, {
      method: "POST",
    }),

  // US-ERP-02-03: Lots
  listLots: (filters: { product_sku?: string; quality_status?: string } = {}): Promise<InventoryLotRead[]> =>
    authedFetch<InventoryLotRead[]>(`${BASE}/lots${buildQuery(filters)}`),

  getLot: (lotId: string): Promise<InventoryLotRead> =>
    authedFetch<InventoryLotRead>(`${BASE}/lots/${lotId}`),

  patchLotQuality: (lotId: string, quality_status: string): Promise<InventoryLotRead> =>
    authedFetch<InventoryLotRead>(`${BASE}/lots/${lotId}/quality-status`, {
      method: "PATCH",
      body: JSON.stringify({ quality_status }),
    }),

  getLotTraceability: (lotId: string): Promise<LotTraceabilityRead> =>
    authedFetch<LotTraceabilityRead>(`${BASE}/lots/${lotId}/traceability`),

  // US-ERP-02-04: Warehouses
  listWarehouses: (): Promise<WarehouseRead[]> =>
    authedFetch<WarehouseRead[]>(WH_BASE),

  createWarehouse: (payload: WarehouseCreate): Promise<WarehouseRead> =>
    authedFetch<WarehouseRead>(WH_BASE, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listZones: (warehouseId: string): Promise<WarehouseZoneRead[]> =>
    authedFetch<WarehouseZoneRead[]>(`${WH_BASE}/${warehouseId}/zones`),

  createZone: (warehouseId: string, payload: WarehouseZoneCreate): Promise<WarehouseZoneRead> =>
    authedFetch<WarehouseZoneRead>(`${WH_BASE}/${warehouseId}/zones`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listLocations: (warehouseId: string, zoneId: string): Promise<WarehouseLocationRead[]> =>
    authedFetch<WarehouseLocationRead[]>(`${WH_BASE}/${warehouseId}/zones/${zoneId}/locations`),

  // US-ERP-02-05: FEFO + expiry alerts
  listExpiryAlerts: (filters: { warehouse_id?: string; threshold_days?: number } = {}): Promise<ExpiryAlertGroupRead[]> =>
    authedFetch<ExpiryAlertGroupRead[]>(`${BASE}/expiry-alerts${buildQuery(filters)}`),

  suggestFefo: (payload: FEFOPickRequest): Promise<FEFOPickSuggestion> =>
    authedFetch<FEFOPickSuggestion>(`${BASE}/picking/suggest`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // US-ERP-02-06: Replenishment params
  listReplenishmentParams: (filters: { warehouse_id?: string; active_only?: boolean } = {}): Promise<ReplenishmentParamRead[]> =>
    authedFetch<ReplenishmentParamRead[]>(`${BASE}/replenishment-params${buildQuery(filters)}`),

  createReplenishmentParam: (payload: ReplenishmentParamCreate): Promise<ReplenishmentParamRead> =>
    authedFetch<ReplenishmentParamRead>(`${BASE}/replenishment-params`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  patchReplenishmentParam: (id: string, payload: Partial<ReplenishmentParamCreate>): Promise<ReplenishmentParamRead> =>
    authedFetch<ReplenishmentParamRead>(`${BASE}/replenishment-params/${id}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),

  runRopCheck: (): Promise<RopCheckResult> =>
    authedFetch<RopCheckResult>(`${BASE}/replenishment-params/run-rop-check`, {
      method: "POST",
    }),

  // US-ERP-02-07: ABC classification + cycle count schedules
  listAbcClassifications: (filters: { warehouse_id?: string; abc_class?: string } = {}): Promise<ProductAbcClassificationRead[]> =>
    authedFetch<ProductAbcClassificationRead[]>(`${BASE}/abc-classifications${buildQuery(filters)}`),

  listCycleCountSchedules: (filters: { warehouse_id?: string } = {}): Promise<CycleCountScheduleRead[]> =>
    authedFetch<CycleCountScheduleRead[]>(`${BASE}/cycle-count-schedules${buildQuery(filters)}`),

  // US-ERP-02-08: KPIs
  getKpis: (): Promise<InventoryKpisRead> =>
    authedFetch<InventoryKpisRead>(`${BASE}/kpis`),
};

// ---------------------------------------------------------------------------
// Types — US-ERP-02-05/06/07/08
// ---------------------------------------------------------------------------

export interface ExpiryAlertItem {
  lot_id: string;
  lot_number: string;
  expiry_date: string;
  days_until_expiry: number;
  qty_on_hand: string;
  warehouse_id: string | null;
  quality_status: string;
}

export interface ExpiryAlertGroupRead {
  product_sku: string;
  threshold_days: number;
  lots: ExpiryAlertItem[];
}

export interface FEFOPickRequest {
  product_sku: string;
  warehouse_id: string;
  qty_needed: number;
}

export interface FEFOLotItem {
  lot_id: string;
  lot_number: string;
  expiry_date: string | null;
  qty_available: string;
  qty_to_pick: string;
}

export interface FEFOPickSuggestion {
  product_sku: string;
  warehouse_id: string;
  qty_needed: string;
  lots: FEFOLotItem[];
}

export interface ReplenishmentParamRead {
  id: string;
  product_sku: string;
  warehouse_id: string;
  reorder_point: string;
  safety_stock: string;
  reorder_qty: string;
  lead_time_days: number;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface ReplenishmentParamCreate {
  product_sku: string;
  warehouse_id: string;
  reorder_point?: number;
  safety_stock?: number;
  reorder_qty?: number;
  lead_time_days?: number;
  is_active?: boolean;
}

export interface RopCheckResult {
  prs_created: number;
  sku_breaches: string[];
}

export interface ProductAbcClassificationRead {
  id: string;
  product_sku: string;
  warehouse_id: string;
  abc_class: "A" | "B" | "C";
  annual_consumption_value: string;
  pct_of_total: string;
  classified_at: string;
}

export interface CycleCountScheduleRead {
  id: string;
  warehouse_id: string;
  abc_class: "A" | "B" | "C";
  frequency_days: number;
  next_count_date: string | null;
  last_count_date: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface InventoryKpisRead {
  inventory_turnover: string | null;
  days_on_hand: string | null;
  fill_rate_pct: string | null;
  stockout_count: number;
  expiry_alert_count: number;
  rop_breach_count: number;
  computed_at: string;
}
