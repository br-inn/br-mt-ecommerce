"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SOStatus =
  | "draft"
  | "confirmed"
  | "in_fulfillment"
  | "partially_delivered"
  | "delivered"
  | "invoiced"
  | "closed"
  | "cancelled"
  | "on_credit_hold";

export type SOOrderType =
  | "STANDARD"
  | "RUSH"
  | "CASH"
  | "CONTRACT_RELEASE"
  | "RETURN";

export type DeliveryStatus =
  | "pending_pick"
  | "picking"
  | "packed"
  | "goods_issued"
  | "cancelled";

export type RmaStatus =
  | "requested"
  | "approved"
  | "goods_received"
  | "credit_issued"
  | "closed"
  | "rejected";

export interface SalesOrderLineOut {
  id: string;
  so_id: string;
  product_sku: string;
  qty: string;
  uom: string;
  unit_price: string | null;
  discount_pct: string;
  line_total: string | null;
  confirmed_qty: string | null;
  requested_delivery_date: string | null;
  status: string;
}

export interface SalesOrderRead {
  id: string;
  so_number: string;
  customer_id: string;
  order_type: SOOrderType;
  quotation_id: string | null;
  status: SOStatus;
  warehouse_id: string | null;
  requested_delivery_date: string | null;
  payment_terms: string | null;
  currency: string | null;
  subtotal: string | null;
  tax_amount: string | null;
  total_amount: string | null;
  notes: string | null;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  lines: SalesOrderLineOut[];
}

export interface SalesOrderListOut {
  items: SalesOrderRead[];
  total: number;
}

export interface ATPLineResult {
  so_line_id: string;
  product_sku: string;
  requested_qty: string;
  atp_qty: string;
  status: "available" | "partial" | "backorder";
  confirmed_date: string | null;
  first_available_date: string | null;
}

export interface ATPCheckOut {
  so_id: string;
  lines: ATPLineResult[];
}

export interface O2CKpisOut {
  open_so_count: number;
  backorder_count: number;
  on_time_delivery_pct: number;
  avg_order_value: string;
  open_credit_holds: number;
  rma_open_count: number;
}

export interface BackorderLineOut {
  so_line_id: string;
  so_number: string;
  product_sku: string;
  qty: string;
  confirmed_qty: string | null;
  first_available_date: string | null;
  customer_id: string;
  requested_delivery_date: string | null;
}

export interface OutboundDeliveryLineOut {
  id: string;
  delivery_id: string;
  so_line_id: string;
  product_sku: string;
  qty_planned: string;
  qty_picked: string;
  lot_id: string | null;
  location_id: string | null;
}

export interface OutboundDeliveryRead {
  id: string;
  delivery_number: string;
  so_id: string;
  warehouse_id: string | null;
  status: DeliveryStatus;
  partial_delivery_allowed: boolean;
  shipped_at: string | null;
  created_at: string;
  lines: OutboundDeliveryLineOut[];
}

export interface DocumentChainOut {
  so: SalesOrderRead;
  deliveries: OutboundDeliveryRead[];
  invoices: unknown[];
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

async function authHeaders(): Promise<HeadersInit> {
  const supabase = createSupabaseBrowserClient();
  const { data } = await supabase.auth.getSession();
  const token = data.session?.access_token ?? "";
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${token}`,
  };
}

const BASE = `${env.NEXT_PUBLIC_BACKEND_URL}/api/v1/sales`;

// ---------------------------------------------------------------------------
// Sales Orders
// ---------------------------------------------------------------------------

export const salesApi = {
  async listOrders(params?: {
    status?: SOStatus | "";
    customer_id?: string;
    limit?: number;
    offset?: number;
  }): Promise<SalesOrderListOut> {
    const headers = await authHeaders();
    const qs = new URLSearchParams();
    if (params?.status) qs.set("status", params.status);
    if (params?.customer_id) qs.set("customer_id", params.customer_id);
    if (params?.limit) qs.set("limit", String(params.limit));
    if (params?.offset) qs.set("offset", String(params.offset));
    const res = await fetch(`${BASE}/orders?${qs}`, { headers });
    if (!res.ok) throw new Error(`listOrders: ${res.status}`);
    return res.json();
  },

  async getOrder(id: string): Promise<SalesOrderRead> {
    const headers = await authHeaders();
    const res = await fetch(`${BASE}/orders/${id}`, { headers });
    if (!res.ok) throw new Error(`getOrder: ${res.status}`);
    return res.json();
  },

  async getDocumentChain(id: string): Promise<DocumentChainOut> {
    const headers = await authHeaders();
    const res = await fetch(`${BASE}/orders/${id}/chain`, { headers });
    if (!res.ok) throw new Error(`getDocumentChain: ${res.status}`);
    return res.json();
  },

  async atpCheck(id: string): Promise<ATPCheckOut> {
    const headers = await authHeaders();
    const res = await fetch(`${BASE}/orders/${id}/atp-check`, {
      method: "POST",
      headers,
      body: "{}",
    });
    if (!res.ok) throw new Error(`atpCheck: ${res.status}`);
    return res.json();
  },

  async confirmOrder(id: string): Promise<SalesOrderRead> {
    const headers = await authHeaders();
    const res = await fetch(`${BASE}/orders/${id}/confirm`, {
      method: "POST",
      headers,
      body: "{}",
    });
    if (!res.ok) throw new Error(`confirmOrder: ${res.status}`);
    return res.json();
  },

  // KPIs
  async getKpis(): Promise<O2CKpisOut> {
    const headers = await authHeaders();
    const res = await fetch(`${BASE}/kpis`, { headers });
    if (!res.ok) throw new Error(`getKpis: ${res.status}`);
    return res.json();
  },

  async getBackorders(limit = 100): Promise<BackorderLineOut[]> {
    const headers = await authHeaders();
    const res = await fetch(`${BASE}/backorders?limit=${limit}`, { headers });
    if (!res.ok) throw new Error(`getBackorders: ${res.status}`);
    return res.json();
  },
};
