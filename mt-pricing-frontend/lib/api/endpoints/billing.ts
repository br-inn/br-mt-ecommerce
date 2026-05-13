"use client";

import env from "@/lib/env";
import { createSupabaseBrowserClient } from "@/lib/supabase/client";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type InvoiceType =
  | "STANDARD"
  | "CREDIT_MEMO"
  | "DEBIT_MEMO"
  | "PROFORMA"
  | "INTERCOMPANY";

export type InvoiceStatus = "draft" | "posted" | "cancelled" | "reversed";

export type EInvoiceStatus =
  | "not_required"
  | "pending"
  | "compliant"
  | "rejected";

export interface InvoiceLineRead {
  id: string;
  invoice_id: string;
  product_sku: string;
  so_line_id: string | null;
  description: string | null;
  qty: string;
  unit_price: string;
  discount_pct: string;
  tax_rate: string;
  line_total: string | null;
  tax_amount: string | null;
}

export interface InvoiceRead {
  id: string;
  invoice_number: string;
  invoice_type: InvoiceType;
  delivery_id: string | null;
  so_id: string | null;
  customer_id: string;
  invoice_date: string;
  due_date: string | null;
  subtotal: string | null;
  tax_amount: string;
  total_amount: string | null;
  currency: string;
  status: InvoiceStatus;
  accounting_document_id: string | null;
  payment_terms: string;
  e_invoice_status: EInvoiceStatus;
  created_by: string | null;
  created_at: string;
  updated_at: string;
  lines: InvoiceLineRead[];
}

export interface BillingKPIs {
  dso: string | null;
  cei: string | null;
  time_to_invoice_avg_hours: string | null;
  e_invoice_compliance_pct: string | null;
  overdue_invoice_count: number;
  overdue_amount: string;
}

export interface ARAgingBucket {
  customer_id: string;
  current: string;
  days_1_30: string;
  days_31_60: string;
  days_61_90: string;
  days_90_plus: string;
  total_outstanding: string;
}

export interface ARAgingReport {
  as_of_date: string;
  buckets: ARAgingBucket[];
}

export interface DunningItem {
  invoice_id: string;
  invoice_number: string;
  customer_id: string;
  due_date: string;
  days_overdue: number;
  dunning_level: number;
  total_amount: string;
}

// ---------------------------------------------------------------------------
// API client helpers
// ---------------------------------------------------------------------------

async function getAuthHeaders(): Promise<Record<string, string>> {
  const supabase = createSupabaseBrowserClient();
  const {
    data: { session },
  } = await supabase.auth.getSession();
  if (!session?.access_token) throw new Error("No auth session");
  return {
    "Content-Type": "application/json",
    Authorization: `Bearer ${session.access_token}`,
  };
}

const BASE = `${env.NEXT_PUBLIC_API_URL ?? ""}/api/v1/billing`;

async function get<T>(path: string): Promise<T> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE}${path}`, { headers });
  if (!res.ok) throw new Error(`GET ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const headers = await getAuthHeaders();
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`POST ${path} → ${res.status}`);
  return res.json() as Promise<T>;
}

// ---------------------------------------------------------------------------
// billingApi
// ---------------------------------------------------------------------------

export const billingApi = {
  /** GET /billing/kpis */
  getKpis: () => get<BillingKPIs>("/kpis"),

  /** GET /billing/invoices */
  listInvoices: (params?: {
    customer_id?: string;
    status?: InvoiceStatus;
    limit?: number;
    offset?: number;
  }) => {
    const qs = new URLSearchParams();
    if (params?.customer_id) qs.set("customer_id", params.customer_id);
    if (params?.status) qs.set("status", params.status);
    if (params?.limit !== undefined) qs.set("limit", String(params.limit));
    if (params?.offset !== undefined) qs.set("offset", String(params.offset));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return get<InvoiceRead[]>(`/invoices${query}`);
  },

  /** GET /billing/invoices/{id} */
  getInvoice: (id: string) => get<InvoiceRead>(`/invoices/${id}`),

  /** POST /billing/invoices/{id}/post */
  postInvoice: (id: string) => post<InvoiceRead>(`/invoices/${id}/post`),

  /** POST /billing/invoices/{id}/cancel */
  cancelInvoice: (id: string) => post<InvoiceRead>(`/invoices/${id}/cancel`),

  /** GET /billing/ar-aging */
  getArAging: (as_of_date?: string) => {
    const qs = as_of_date ? `?as_of_date=${as_of_date}` : "";
    return get<ARAgingReport>(`/ar-aging${qs}`);
  },

  /** GET /billing/dunning */
  getDunning: (params?: { customer_id?: string; level?: number }) => {
    const qs = new URLSearchParams();
    if (params?.customer_id) qs.set("customer_id", params.customer_id);
    if (params?.level !== undefined) qs.set("level", String(params.level));
    const query = qs.toString() ? `?${qs.toString()}` : "";
    return get<DunningItem[]>(`/dunning${query}`);
  },
};
