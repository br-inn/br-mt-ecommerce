"""Schemas Pydantic v2 para Goods Receipts — EP-INV-01 (US-INV-01-04)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.purchase_orders import PurchaseOrderLineRead


# ---------------------------------------------------------------------------
# Create / Input
# ---------------------------------------------------------------------------


class GoodsReceiptCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    po_line_id: UUID
    qty_received: Decimal = Field(gt=0)
    received_at: datetime | None = None
    actual_unit_price: Decimal | None = Field(default=None, ge=0)
    actual_breakdown: dict[str, Any] = Field(default_factory=dict)
    notes: str | None = None
    force: bool = Field(
        default=False,
        description="Permite recibir más cantidad que la pedida (override).",
    )


# ---------------------------------------------------------------------------
# Read / Output
# ---------------------------------------------------------------------------


class GoodsReceiptRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    po_line_id: UUID
    qty_received: Decimal
    received_at: datetime
    received_by: UUID | None
    actual_unit_price: Decimal | None
    actual_breakdown: dict[str, Any]
    map_before: Decimal | None
    map_after: Decimal | None
    fx_rate_id: UUID | None
    notes: str | None
    status: str  # pending | processed | error
    processed_at: datetime | None
    created_at: datetime
    po_line: PurchaseOrderLineRead


class GoodsReceiptStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    gr_id: UUID
    status: str
    map_before: Decimal | None
    map_after: Decimal | None
    processed_at: datetime | None
    error_summary: str | None = None  # primeras 200 chars de notes si status='error'
