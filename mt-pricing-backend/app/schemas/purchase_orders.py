"""Pydantic V2 schemas para Purchase Orders / Lines (EP-INV-01 US-INV-01-03)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Purchase Order Line
# ---------------------------------------------------------------------------
_PO_TYPES = ("STANDARD", "BLANKET", "CONTRACT", "SCHEDULING")


class PurchaseOrderLineCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sku: str = Field(min_length=1, max_length=64)
    scheme_code: str = Field(min_length=1, max_length=32)
    qty_ordered: Decimal = Field(gt=0)
    unit_price: Decimal = Field(ge=0)
    landed_cost_breakdown: dict[str, Any] = Field(default_factory=dict)


class PurchaseOrderLineRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    po_id: UUID
    sku: str
    scheme_code: str
    qty_ordered: Decimal
    qty_received: Decimal
    unit_price: Decimal
    landed_cost_breakdown: dict[str, Any]
    price_source: str
    created_at: datetime
    updated_at: datetime


class PurchaseOrderLineUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    qty_ordered: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, ge=0)
    landed_cost_breakdown: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Purchase Order
# ---------------------------------------------------------------------------
class PurchaseOrderCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    po_number: str = Field(min_length=1, max_length=64)
    supplier_code: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    po_type: str = Field(default="STANDARD", max_length=32)
    notes: str | None = None
    lines: list[PurchaseOrderLineCreate] = Field(default_factory=list)


class PurchaseOrderRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    po_number: str
    supplier_code: str | None
    currency: str | None
    po_type: str
    notes: str | None
    status: str
    confirmed_at: datetime | None
    created_by: UUID | None
    created_at: datetime
    updated_at: datetime


class PurchaseOrderReadDetail(PurchaseOrderRead):
    lines: list[PurchaseOrderLineRead] = Field(default_factory=list)
    gr_count: int = 0


class PurchaseOrderUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    po_number: str | None = Field(default=None, min_length=1, max_length=64)
    supplier_code: str | None = Field(default=None, max_length=64)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    notes: str | None = None
