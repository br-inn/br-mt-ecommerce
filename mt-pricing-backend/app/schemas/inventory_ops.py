"""Schemas Pydantic — EP-ERP-02 stories 05-08.

US-ERP-02-05: FEFO + expiry alerts
US-ERP-02-06: Replenishment params + ROP
US-ERP-02-07: ABC classification + cycle count schedules
US-ERP-02-08: KPIs de inventario
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# US-ERP-02-05: Expiry alerts
# ---------------------------------------------------------------------------


class ExpiryAlertThresholdRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_sku: str
    threshold_days: int
    created_at: datetime
    updated_at: datetime


class ExpiryAlertThresholdCreate(BaseModel):
    product_sku: str = Field(..., max_length=200)
    threshold_days: int = Field(default=30, ge=1, le=3650)


class ExpiryAlertThresholdPatch(BaseModel):
    threshold_days: int = Field(..., ge=1, le=3650)


class InventoryAlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    alert_type: str
    product_sku: str
    lot_id: UUID | None
    warehouse_id: UUID | None
    severity: str
    payload: dict
    resolved_at: datetime | None
    created_at: datetime


class ExpiryAlertItem(BaseModel):
    """Item individual dentro del grupo de alertas por producto."""

    lot_id: UUID
    lot_number: str
    expiry_date: date
    days_until_expiry: int
    qty_on_hand: Decimal
    warehouse_id: UUID | None
    quality_status: str


class ExpiryAlertGroupRead(BaseModel):
    """Lotes próximos a vencer agrupados por producto."""

    product_sku: str
    threshold_days: int
    lots: list[ExpiryAlertItem]


class FEFOPickSuggestion(BaseModel):
    """Sugerencia de picking FEFO para un producto."""

    product_sku: str
    warehouse_id: UUID
    qty_needed: Decimal
    lots: list[FEFOLotItem]


class FEFOLotItem(BaseModel):
    lot_id: UUID
    lot_number: str
    expiry_date: date | None
    qty_available: Decimal
    qty_to_pick: Decimal


class FEFOPickRequest(BaseModel):
    product_sku: str = Field(..., max_length=200)
    warehouse_id: UUID
    qty_needed: Decimal = Field(..., gt=0)


# ---------------------------------------------------------------------------
# US-ERP-02-06: Replenishment params
# ---------------------------------------------------------------------------


class ReplenishmentParamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_sku: str
    warehouse_id: UUID
    reorder_point: Decimal
    safety_stock: Decimal
    reorder_qty: Decimal
    lead_time_days: int
    is_active: bool
    created_at: datetime
    updated_at: datetime


class ReplenishmentParamCreate(BaseModel):
    product_sku: str = Field(..., max_length=200)
    warehouse_id: UUID
    reorder_point: Decimal = Field(default=Decimal("0"), ge=0)
    safety_stock: Decimal = Field(default=Decimal("0"), ge=0)
    reorder_qty: Decimal = Field(default=Decimal("1"), gt=0)
    lead_time_days: int = Field(default=7, ge=0)
    is_active: bool = True


class ReplenishmentParamPatch(BaseModel):
    reorder_point: Decimal | None = Field(default=None, ge=0)
    safety_stock: Decimal | None = Field(default=None, ge=0)
    reorder_qty: Decimal | None = Field(default=None, gt=0)
    lead_time_days: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class RopCheckResult(BaseModel):
    """Resultado del job ROP: lista de PRs creadas."""

    prs_created: int
    sku_breaches: list[str]


# ---------------------------------------------------------------------------
# US-ERP-02-07: ABC classification + cycle count schedules
# ---------------------------------------------------------------------------


class ProductAbcClassificationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_sku: str
    warehouse_id: UUID
    abc_class: str
    annual_consumption_value: Decimal
    pct_of_total: Decimal
    classified_at: datetime


class CycleCountScheduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    warehouse_id: UUID
    abc_class: str
    frequency_days: int
    next_count_date: date | None
    last_count_date: date | None
    is_active: bool
    created_at: datetime
    updated_at: datetime


class CycleCountScheduleCreate(BaseModel):
    warehouse_id: UUID
    abc_class: str = Field(..., pattern="^[ABC]$")
    frequency_days: int = Field(..., gt=0)
    next_count_date: date | None = None
    is_active: bool = True


class AbcClassificationRunResult(BaseModel):
    """Resultado de la clasificación ABC mensual."""

    warehouse_id: UUID | None
    products_classified: int
    class_a_count: int
    class_b_count: int
    class_c_count: int
    run_at: datetime


# ---------------------------------------------------------------------------
# US-ERP-02-08: KPIs de inventario
# ---------------------------------------------------------------------------


class InventoryKpisRead(BaseModel):
    """KPIs agregados de inventario para el dashboard."""

    inventory_turnover: Decimal | None = Field(
        None,
        description="COGS / avg_inventory_value (últimos 30 días). None si no hay datos.",
    )
    days_on_hand: Decimal | None = Field(
        None,
        description="(avg_inventory_value / COGS) * 30. None si no hay datos.",
    )
    fill_rate_pct: Decimal | None = Field(
        None,
        description="% pedidos completados sin stockout (aproximación desde GR).",
    )
    stockout_count: int = Field(
        ...,
        description="Productos con qty_on_hand <= 0.",
    )
    expiry_alert_count: int = Field(
        ...,
        description="Lotes con expiry_date < today + 30 días.",
    )
    rop_breach_count: int = Field(
        ...,
        description="Productos con qty_on_hand <= reorder_point activo.",
    )
    computed_at: datetime


class CriticalStockItem(BaseModel):
    """Producto con stock crítico para tabla del dashboard."""

    product_sku: str
    qty_on_hand: Decimal
    reorder_point: Decimal | None
    days_on_hand: Decimal | None
    expiry_alert: bool
