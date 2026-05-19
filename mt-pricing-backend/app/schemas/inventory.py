"""Schemas Pydantic v2 para Inventory — EP-INV-01 + EP-ERP-02."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# EP-INV-01
# ---------------------------------------------------------------------------


class InventoryPositionRead(BaseModel):
    """Posición de inventario 5D (SKU × proveedor × esquema × lot × stock_type)."""

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
    warehouse_id: UUID | None = None
    lot_id: UUID | None = None
    location_id: UUID | None = None
    stock_type: str = "unrestricted"
    # Join desde products
    product_name: str | None = None


class InventoryAvailabilityRead(BaseModel):
    """Disponibilidad unrestricted de un SKU, agrupada por almacén."""

    model_config = ConfigDict(from_attributes=True)

    product_sku: str | None
    sku: str
    warehouse_id: UUID | None
    qty_available: Decimal


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


# ---------------------------------------------------------------------------
# US-ERP-02-01: Movement Types + Movements
# ---------------------------------------------------------------------------


class StockMovementTypeRead(BaseModel):
    """Tipo de movimiento SAP-MM."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    direction: str
    requires_reference: bool
    posts_accounting: bool
    is_active: bool


class StockMovementCreate(BaseModel):
    """Payload para crear un movimiento de stock."""

    movement_type_id: UUID
    product_sku: str
    qty: Decimal
    lot_id: UUID | None = None
    warehouse_id: UUID | None = None
    location_id: UUID | None = None
    reference_id: UUID | None = None
    reference_type: str | None = None
    notes: str | None = None


class JournalEntryRead(BaseModel):
    """Asiento contable generado por un movimiento."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_movement_id: UUID
    debit_account: str
    credit_account: str
    amount: Decimal
    currency: str
    posted_at: datetime


class StockMovementRead(BaseModel):
    """Movimiento de stock con asientos opcionales."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    movement_type_id: UUID
    product_sku: str
    qty: Decimal
    lot_id: UUID | None
    warehouse_id: UUID | None
    location_id: UUID | None
    reference_id: UUID | None
    reference_type: str | None
    reversal_of: UUID | None
    posted_at: datetime
    posted_by: UUID | None
    notes: str | None
    journal_entries: list[JournalEntryRead] = []


# ---------------------------------------------------------------------------
# US-ERP-02-03: Lot tracking
# ---------------------------------------------------------------------------


class InventoryLotRead(BaseModel):
    """Lote de inventario con datos de trazabilidad."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    lot_number: str
    product_sku: str
    manufacture_date: date | None
    expiry_date: date | None
    country_of_origin: str | None
    quality_status: str
    po_line_id: UUID | None
    created_at: datetime


class InventoryLotQualityPatch(BaseModel):
    """Payload para cambiar el quality_status de un lote."""

    quality_status: str


class TraceabilityUpstream(BaseModel):
    """Trazabilidad hacia atrás: lote → PO line → vendor."""

    lot_id: UUID
    lot_number: str
    po_line_id: UUID | None
    po_number: str | None
    supplier_code: str | None


class TraceabilityDownstream(BaseModel):
    """Trazabilidad hacia adelante: lote → stock movements de salida."""

    movement_id: UUID
    movement_type_code: str
    qty: Decimal
    reference_id: UUID | None
    reference_type: str | None
    posted_at: datetime


class LotTraceabilityRead(BaseModel):
    """Resultado completo de trazabilidad de un lote."""

    lot: InventoryLotRead
    upstream: TraceabilityUpstream
    downstream: list[TraceabilityDownstream]


# ---------------------------------------------------------------------------
# US-ERP-02-04: Warehouses
# ---------------------------------------------------------------------------


class WarehouseCreate(BaseModel):
    code: str
    name: str
    address: str | None = None


class WarehouseRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    address: str | None
    is_active: bool


class WarehousePatch(BaseModel):
    """Campos opcionales para PATCH /warehouses/{id} — US-ERP-02-04."""

    model_config = ConfigDict(from_attributes=True)

    name: str | None = None
    country: str | None = None
    is_active: bool | None = None
    fefo_enabled: bool | None = None


class WarehouseZoneCreate(BaseModel):
    code: str
    name: str
    zone_type: str | None = None


class WarehouseZoneRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    warehouse_id: UUID
    code: str
    name: str
    zone_type: str | None


class WarehouseLocationCreate(BaseModel):
    bin_code: str
    max_weight: Decimal | None = None


class WarehouseLocationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    zone_id: UUID
    bin_code: str
    is_active: bool
    max_weight: Decimal | None


class WarehouseDetailRead(BaseModel):
    """Almacén con sus zonas (y cada zona con sus locations)."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    address: str | None
    is_active: bool
    zones: list[WarehouseZoneRead] = []
