"""Pydantic V2 schemas — EP-ERP-03 (Compras P2P)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Purchase Requisition
# ---------------------------------------------------------------------------


class PRCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_sku: str | None = None
    qty: Decimal = Field(gt=0)
    uom: str = Field(default="UNIT", max_length=32)
    required_date: date | None = None
    cost_center_id: str | None = Field(default=None, max_length=64)
    suggested_vendor_id: UUID | None = None
    estimated_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class PROut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    pr_number: str
    requester_id: UUID
    product_sku: str | None
    qty: Decimal
    uom: str
    required_date: date | None
    cost_center_id: str | None
    suggested_vendor_id: UUID | None
    estimated_amount: Decimal | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PRSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PRReject(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Approval Decision
# ---------------------------------------------------------------------------


class ApprovalDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    document_id: UUID
    document_type: str
    approver_id: UUID
    action: str
    reason: str | None
    decided_at: datetime


# ---------------------------------------------------------------------------
# Approval Rule
# ---------------------------------------------------------------------------


class ApprovalRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_type: str = Field(default="purchase_requisition", max_length=64)
    min_amount: Decimal = Field(default=Decimal("0"), ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    category_id: str | None = Field(default=None, max_length=64)
    approver_role: str | None = Field(default=None, max_length=32)
    approver_user_id: UUID | None = None
    timeout_hours: int = Field(default=48, ge=0)
    priority: int = Field(default=0, ge=0)
    is_active: bool = True


class ApprovalRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    document_type: str
    min_amount: Decimal
    max_amount: Decimal | None
    category_id: str | None
    approver_role: str | None
    approver_user_id: UUID | None
    timeout_hours: int
    priority: int
    is_active: bool
    created_at: datetime


class ApprovalRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    category_id: str | None = None
    approver_role: str | None = Field(default=None, max_length=32)
    approver_user_id: UUID | None = None
    timeout_hours: int | None = Field(default=None, ge=0)
    priority: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Vendor Product Condition (PIR)
# ---------------------------------------------------------------------------


class VendorConditionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_id: str = Field(min_length=1, max_length=64)
    product_sku: str = Field(min_length=1)
    price: Decimal = Field(ge=0)
    uom: str = Field(default="UNIT", max_length=32)
    moq: int = Field(default=1, ge=1)
    lead_time_days: int | None = Field(default=None, ge=0)
    valid_from: date | None = None
    valid_to: date | None = None
    currency: str = Field(default="AED", min_length=3, max_length=3)
    is_active: bool = True


class VendorConditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    vendor_id: str
    product_sku: str
    price: Decimal
    uom: str
    moq: int
    lead_time_days: int | None
    valid_from: date
    valid_to: date | None
    currency: str
    is_active: bool
    created_at: datetime


class VendorConditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    price: Decimal | None = Field(default=None, ge=0)
    uom: str | None = Field(default=None, max_length=32)
    moq: int | None = Field(default=None, ge=1)
    lead_time_days: int | None = Field(default=None, ge=0)
    valid_to: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Vendor Invoices (US-ERP-03-04 — 3-way match)
# ---------------------------------------------------------------------------


class VendorInvoiceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    invoice_number: str = Field(min_length=1, max_length=128)
    vendor_id: str = Field(min_length=1, max_length=128)
    po_id: UUID
    gr_id: UUID | None = None
    invoice_date: date
    total_amount: Decimal = Field(ge=0)
    currency: str = Field(default="AED", min_length=3, max_length=3)


class VendorInvoiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    invoice_number: str
    vendor_id: str
    po_id: UUID
    gr_id: UUID | None
    invoice_date: date
    total_amount: Decimal
    currency: str
    status: str
    payment_block: bool
    match_details: dict | None
    created_at: datetime


class InvoiceReleaseBlock(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1)


class InvoiceToleranceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_type: str = Field(default="vendor_invoice", max_length=64)
    vendor_category: str | None = None
    tolerance_key: str = Field(min_length=1, max_length=128)
    absolute_limit: Decimal | None = Field(default=None, ge=0)
    pct_limit: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="AED", min_length=3, max_length=3)
    is_active: bool = True


class InvoiceToleranceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    document_type: str
    vendor_category: str | None
    tolerance_key: str
    absolute_limit: Decimal | None
    pct_limit: Decimal | None
    currency: str
    is_active: bool


class InvoiceToleranceUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    absolute_limit: Decimal | None = Field(default=None, ge=0)
    pct_limit: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Source List (US-ERP-03-05)
# ---------------------------------------------------------------------------


class SourceListCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_sku: str = Field(min_length=1)
    vendor_id: str = Field(min_length=1, max_length=128)
    vendor_name: str | None = None
    is_preferred: bool = False
    is_blocked: bool = False
    valid_from: date | None = None
    valid_to: date | None = None
    fixed_source: bool = False
    notes: str | None = None


class SourceListOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    product_sku: str
    vendor_id: str
    vendor_name: str | None
    is_preferred: bool
    is_blocked: bool
    valid_from: date
    valid_to: date | None
    fixed_source: bool
    notes: str | None


class SourceListUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_name: str | None = None
    is_preferred: bool | None = None
    is_blocked: bool | None = None
    valid_to: date | None = None
    fixed_source: bool | None = None
    notes: str | None = None


# ---------------------------------------------------------------------------
# RFQ (US-ERP-03-05)
# ---------------------------------------------------------------------------


class RfqLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_sku: str = Field(min_length=1)
    qty: Decimal = Field(gt=0)
    uom: str = Field(default="UNIT", max_length=32)


class RfqLineOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    rfq_id: UUID
    product_sku: str
    qty: Decimal
    uom: str


class RfqCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    pr_id: UUID | None = None
    deadline: date | None = None
    notes: str | None = None
    lines: list[RfqLineCreate] = Field(min_length=1)


class RfqOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    rfq_number: str
    pr_id: UUID | None
    status: str
    deadline: date | None
    notes: str | None
    created_at: datetime
    created_by: UUID


class RfqResponseCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_id: str = Field(min_length=1, max_length=128)
    unit_price: Decimal | None = Field(default=None, ge=0)
    currency: str = Field(default="AED", min_length=3, max_length=3)
    lead_time_days: int | None = Field(default=None, ge=0)
    valid_until: date | None = None
    notes: str | None = None


class RfqResponseOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    rfq_id: UUID
    vendor_id: str
    unit_price: Decimal | None
    currency: str
    lead_time_days: int | None
    valid_until: date | None
    notes: str | None
    responded_at: datetime | None


class RfqComparisonItem(BaseModel):
    """Un renglón en la tabla comparativa de respuestas RFQ."""

    vendor_id: str
    unit_price: Decimal | None
    currency: str
    lead_time_days: int | None
    score: float | None
    """Score compuesto: 0.6*(1/precio_norm) + 0.4*(1/lead_time_norm). Mayor es mejor."""


class RfqComparisonOut(BaseModel):
    rfq_id: UUID
    rfq_number: str
    items: list[RfqComparisonItem]


# ---------------------------------------------------------------------------
# KPIs Dashboard (US-ERP-03-06)
# ---------------------------------------------------------------------------


class ProcurementKpiOut(BaseModel):
    """KPIs consolidados del módulo de compras."""

    open_pr_count: int
    open_po_count: int
    pending_invoice_count: int
    blocked_invoice_amount: Decimal
    maverick_spend_pct: Decimal
    avg_po_lead_time_days: Decimal | None
    on_time_delivery_pct: Decimal | None


class SpendByVendor(BaseModel):
    vendor_id: str
    total_amount: Decimal


class SpendByProduct(BaseModel):
    product_sku: str
    total_amount: Decimal


class SpendAnalysisOut(BaseModel):
    period_days: int
    by_vendor: list[SpendByVendor]
    by_product: list[SpendByProduct]
