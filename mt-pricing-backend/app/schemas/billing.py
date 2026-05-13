"""Schemas Pydantic — Billing & Facturación (EP-ERP-05)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Invoice
# ---------------------------------------------------------------------------

class InvoiceLineCreate(BaseModel):
    product_sku: str
    so_line_id: UUID | None = None
    description: str | None = None
    qty: Decimal
    unit_price: Decimal
    discount_pct: Decimal = Decimal("0")
    tax_rate: Decimal = Decimal("5")


class InvoiceLineRead(BaseModel):
    id: UUID
    invoice_id: UUID
    product_sku: str
    so_line_id: UUID | None
    description: str | None
    qty: Decimal
    unit_price: Decimal
    discount_pct: Decimal
    tax_rate: Decimal
    line_total: Decimal | None
    tax_amount: Decimal | None

    model_config = {"from_attributes": True}


class InvoiceCreate(BaseModel):
    invoice_number: str
    invoice_type: str = "STANDARD"
    delivery_id: UUID | None = None
    so_id: UUID | None = None
    customer_id: str
    invoice_date: date | None = None
    due_date: date | None = None
    currency: str = "AED"
    payment_terms: str = "NET30"
    lines: list[InvoiceLineCreate] = Field(default_factory=list)


class InvoicePatch(BaseModel):
    due_date: date | None = None
    payment_terms: str | None = None
    status: str | None = None
    e_invoice_status: str | None = None


class InvoiceRead(BaseModel):
    id: UUID
    invoice_number: str
    invoice_type: str
    delivery_id: UUID | None
    so_id: UUID | None
    customer_id: str
    invoice_date: date
    due_date: date | None
    subtotal: Decimal | None
    tax_amount: Decimal
    total_amount: Decimal | None
    currency: str
    status: str
    accounting_document_id: UUID | None
    payment_terms: str
    e_invoice_status: str
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    lines: list[InvoiceLineRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class InvoiceChain(BaseModel):
    invoice: InvoiceRead
    so: dict | None = None
    delivery: dict | None = None


# ---------------------------------------------------------------------------
# Dunning
# ---------------------------------------------------------------------------

class DunningLevelRead(BaseModel):
    id: UUID
    level: int
    days_overdue: int
    action: str
    fee_amount: Decimal
    is_active: bool

    model_config = {"from_attributes": True}


class DunningHistoryRead(BaseModel):
    id: UUID
    invoice_id: UUID
    customer_id: str
    dunning_level: int
    sent_at: datetime
    notes: str | None

    model_config = {"from_attributes": True}


class DunningEscalateRequest(BaseModel):
    notes: str | None = None


# ---------------------------------------------------------------------------
# E-Invoice
# ---------------------------------------------------------------------------

class EInvoiceSubmitRequest(BaseModel):
    standard: str = "ZATCA_PHASE2"
    seller_name: str | None = None
    vat_number: str | None = None


class EInvoiceSubmissionRead(BaseModel):
    id: UUID
    invoice_id: UUID
    standard: str
    submission_ref: str | None
    submitted_at: datetime | None
    response_code: str | None
    response_message: str | None
    status: str
    xml_payload: str | None
    qr_code: str | None
    retry_count: int
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Payment Promises
# ---------------------------------------------------------------------------

class PaymentPromiseCreate(BaseModel):
    invoice_id: UUID
    customer_id: str
    promised_date: date
    promised_amount: Decimal | None = None
    notes: str | None = None


class PaymentPromisePatch(BaseModel):
    promised_date: date | None = None
    promised_amount: Decimal | None = None
    status: str | None = None
    notes: str | None = None


class PaymentPromiseRead(BaseModel):
    id: UUID
    invoice_id: UUID
    customer_id: str
    promised_date: date
    promised_amount: Decimal | None
    status: str
    notes: str | None
    created_by: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# AR Aging
# ---------------------------------------------------------------------------

class ARAgingBucket(BaseModel):
    customer_id: str
    current: Decimal = Decimal("0")
    days_1_30: Decimal = Decimal("0")
    days_31_60: Decimal = Decimal("0")
    days_61_90: Decimal = Decimal("0")
    days_90_plus: Decimal = Decimal("0")
    total_outstanding: Decimal = Decimal("0")


class ARAgingReport(BaseModel):
    as_of_date: date
    buckets: list[ARAgingBucket]


# ---------------------------------------------------------------------------
# KPIs
# ---------------------------------------------------------------------------

class BillingKPIs(BaseModel):
    dso: Decimal | None = None
    cei: Decimal | None = None
    time_to_invoice_avg_hours: Decimal | None = None
    e_invoice_compliance_pct: Decimal | None = None
    overdue_invoice_count: int = 0
    overdue_amount: Decimal = Decimal("0")
