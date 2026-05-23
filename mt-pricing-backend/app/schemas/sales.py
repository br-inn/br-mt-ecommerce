"""Pydantic schemas — EP-ERP-04 Ventas O2C.

Sigue el patrón Create / Update / Out del proyecto.
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------


class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# US-ERP-04-01 — Sales Orders
# ---------------------------------------------------------------------------


class SalesOrderLineCreate(BaseModel):
    product_sku: str
    qty: Decimal = Field(gt=0)
    uom: str = "UNIT"
    unit_price: Decimal | None = None
    discount_pct: Decimal = Decimal("0")
    requested_delivery_date: date | None = None


class SalesOrderLineOut(_Base):
    id: UUID
    so_id: UUID
    product_sku: str
    qty: Decimal
    uom: str
    unit_price: Decimal | None
    discount_pct: Decimal
    line_total: Decimal | None
    confirmed_qty: Decimal | None
    requested_delivery_date: date | None
    status: str


class SalesOrderCreate(BaseModel):
    customer_id: str
    order_type: str = "STANDARD"
    quotation_id: UUID | None = None
    warehouse_id: UUID | None = None
    requested_delivery_date: date | None = None
    payment_terms: str | None = None
    currency: str = "AED"
    notes: str | None = None
    lines: list[SalesOrderLineCreate] = Field(default_factory=list)


class SalesOrderUpdate(BaseModel):
    status: str | None = None
    requested_delivery_date: date | None = None
    payment_terms: str | None = None
    notes: str | None = None
    warehouse_id: UUID | None = None


class SalesOrderOut(_Base):
    id: UUID
    so_number: str
    customer_id: str
    order_type: str
    quotation_id: UUID | None
    status: str
    warehouse_id: UUID | None
    requested_delivery_date: date | None
    payment_terms: str | None
    currency: str | None
    subtotal: Decimal | None
    tax_amount: Decimal | None
    total_amount: Decimal | None
    notes: str | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime
    lines: list[SalesOrderLineOut] = Field(default_factory=list)


class SalesOrderListOut(BaseModel):
    items: list[SalesOrderOut]
    total: int


class DocumentChainOut(BaseModel):
    """Respuesta de GET /sales/orders/{id}/chain."""

    so: SalesOrderOut
    deliveries: list[Any] = Field(default_factory=list)
    invoices: list[Any] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# US-ERP-04-02 — ATP check + Reservations
# ---------------------------------------------------------------------------


class ATPLineResult(BaseModel):
    so_line_id: UUID
    product_sku: str
    requested_qty: Decimal
    atp_qty: Decimal
    status: str  # 'available' | 'partial' | 'backorder'
    confirmed_date: date | None
    first_available_date: date | None


class ATPCheckOut(BaseModel):
    so_id: UUID
    lines: list[ATPLineResult]


class StockReservationOut(_Base):
    id: UUID
    so_line_id: UUID
    product_sku: str
    warehouse_id: UUID
    qty: Decimal
    reserved_at: datetime
    expires_at: datetime | None
    status: str


class AtpRuleCreate(BaseModel):
    product_sku: str | None = None
    include_safety_stock: bool = False
    include_planned_receipts: bool = True
    include_qa_stock: bool = False
    horizon_days: int = 30


class AtpRuleOut(_Base):
    id: UUID
    product_sku: str | None
    include_safety_stock: bool
    include_planned_receipts: bool
    include_qa_stock: bool
    horizon_days: int


# ---------------------------------------------------------------------------
# US-ERP-04-03 — Credit Management
# ---------------------------------------------------------------------------


class CreditLimitCreate(BaseModel):
    customer_id: str
    credit_limit: Decimal | None = None
    currency: str = "AED"
    credit_horizon_days: int = 30


class CreditLimitUpdate(BaseModel):
    credit_limit: Decimal | None = None
    currency: str | None = None
    credit_horizon_days: int | None = None
    is_blocked: bool | None = None
    block_reason: str | None = None


class CreditLimitOut(_Base):
    id: UUID
    customer_id: str
    credit_limit: Decimal | None
    currency: str
    credit_horizon_days: int
    is_blocked: bool
    block_reason: str | None
    updated_at: datetime


class CreditCheckOut(BaseModel):
    status: str  # 'ok' | 'warning' | 'blocked' | 'skipped'
    exposure: Decimal
    limit: Decimal | None
    available: Decimal | None
    skipped: bool = False
    reason: str | None = None


class CustomerOpenItemOut(_Base):
    id: UUID
    customer_id: str
    so_id: UUID | None
    invoice_id: UUID | None
    document_type: str
    amount: Decimal
    due_date: date | None
    status: str
    created_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-04-04 — Outbound Delivery
# ---------------------------------------------------------------------------


class OutboundDeliveryLineOut(_Base):
    id: UUID
    delivery_id: UUID
    so_line_id: UUID
    product_sku: str
    qty_planned: Decimal
    qty_picked: Decimal
    lot_id: UUID | None
    location_id: UUID | None


class OutboundDeliveryCreate(BaseModel):
    so_id: UUID
    warehouse_id: UUID | None = None
    partial_delivery_allowed: bool = True
    line_so_line_ids: list[UUID] = Field(default_factory=list)


class OutboundDeliveryStatusUpdate(BaseModel):
    status: str


class OutboundDeliveryOut(_Base):
    id: UUID
    delivery_number: str
    so_id: UUID
    warehouse_id: UUID | None
    status: str
    partial_delivery_allowed: bool
    shipped_at: datetime | None
    created_at: datetime
    lines: list[OutboundDeliveryLineOut] = Field(default_factory=list)


class OutboundDeliveryListOut(BaseModel):
    items: list[OutboundDeliveryOut]
    total: int


# ---------------------------------------------------------------------------
# US-ERP-04-05 — RMA + Credit Memo
# ---------------------------------------------------------------------------


class RmaLineCreate(BaseModel):
    so_line_id: UUID
    product_sku: str
    qty_returned: Decimal = Field(gt=0)
    lot_id: UUID | None = None
    condition: str = "resalable"


class RmaCreate(BaseModel):
    original_so_id: UUID
    customer_id: str
    return_type: str
    reason: str | None = None
    lines: list[RmaLineCreate] = Field(default_factory=list)


class RmaLineOut(_Base):
    id: UUID
    rma_id: UUID
    so_line_id: UUID
    product_sku: str
    qty_returned: Decimal
    lot_id: UUID | None
    condition: str


class RmaOut(_Base):
    id: UUID
    rma_number: str
    original_so_id: UUID
    customer_id: str
    return_type: str
    status: str
    reason: str | None
    created_at: datetime
    lines: list[RmaLineOut] = Field(default_factory=list)


class CreditMemoOut(_Base):
    id: UUID
    memo_number: str
    rma_id: UUID
    customer_id: str
    amount: Decimal
    currency: str
    status: str
    created_at: datetime


class ReturnDeliveryCreate(BaseModel):
    warehouse_id: UUID | None = None
    received_date: date | None = None
    notes: str | None = None


class ReturnDeliveryOut(_Base):
    id: UUID
    rma_id: UUID
    warehouse_id: UUID | None
    received_date: date
    received_by: UUID | None
    notes: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-04-06 — Dashboard KPIs
# ---------------------------------------------------------------------------


class O2CKpisOut(BaseModel):
    open_so_count: int
    backorder_count: int
    on_time_delivery_pct: float
    avg_order_value: Decimal
    open_credit_holds: int
    rma_open_count: int
    revenue_mtd: Decimal = Decimal("0")
    order_count_mtd: int = 0
    fill_rate_pct: float = 0.0


class BackorderLineOut(BaseModel):
    so_line_id: UUID
    so_number: str
    product_sku: str
    qty: Decimal
    confirmed_qty: Decimal | None
    first_available_date: date | None
    customer_id: str
    requested_delivery_date: date | None
