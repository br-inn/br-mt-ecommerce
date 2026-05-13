"""Schemas Pydantic v2 para Inventory Positions — EP-INV-01 (US-INV-01-05)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class InventoryPositionRead(BaseModel):
    """Posición de inventario agregada (SKU × proveedor × esquema)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    sku: str
    supplier_code: str
    scheme_code: str
    qty_on_hand: Decimal
    map_aed: Decimal | None
    total_stock_value_aed: Decimal | None
    last_gr_id: UUID | None
    last_updated_at: datetime | None
    # Join desde products
    product_name: str | None = None


class MAPHistoryPoint(BaseModel):
    """Un punto del historial de cambios MAP para un SKU."""

    model_config = ConfigDict(from_attributes=True)

    gr_id: UUID
    map_before: Decimal | None
    map_after: Decimal
    qty_received: Decimal
    received_at: datetime
    po_number: str


class InventorySummary(BaseModel):
    """KPIs agregados del inventario para el widget de dashboard."""

    total_skus_with_stock: int
    total_stock_value_aed: Decimal
    skus_without_cost: int
    pending_gr_count: int
