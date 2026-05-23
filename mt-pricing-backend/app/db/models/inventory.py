"""Inventory models — EP-INV-01 + EP-ERP-02.

Pipeline completo:
  Purchase Order → Goods Receipt → MAP automático (EP-INV-01)
  Movement Types → Stock Movements → Journal Entries (US-ERP-02-01)
  Inventory Positions 5D (US-ERP-02-02)
  Lot tracking + trazabilidad (US-ERP-02-03)
  Warehouse → Zone → Location hierarchy (US-ERP-02-04)
  FEFO + expiry alerts (US-ERP-02-05)
  Replenishment params + ROP (US-ERP-02-06)
  ABC classification + cycle count schedules (US-ERP-02-07)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CHAR,
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# EP-INV-01: Purchase Order pipeline
# ---------------------------------------------------------------------------


class PurchaseOrder(UuidPkMixin, TimestampMixin, Base):
    """Orden de compra emitida a un proveedor."""

    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    supplier_code: Mapped[str | None] = mapped_column(
        String(64),
        ForeignKey("suppliers.code", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'draft'"),
    )
    currency: Mapped[str | None] = mapped_column(
        String(3),
        ForeignKey("currencies.code", ondelete="RESTRICT"),
        nullable=True,
    )
    po_type: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'STANDARD'"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    lines: Mapped[list[PurchaseOrderLine]] = relationship(
        "PurchaseOrderLine",
        back_populates="purchase_order",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','confirmed','partial','received','cancelled')",
            name="ck_po_status",
        ),
        CheckConstraint(
            "po_type IN ('STANDARD','BLANKET','CONTRACT','SCHEDULING')",
            name="ck_po_type",
        ),
        Index("idx_po_supplier", "supplier_code", "status"),
        Index(
            "idx_po_status",
            "status",
            postgresql_where=text("status NOT IN ('received','cancelled')"),
        ),
    )


class PurchaseOrderLine(UuidPkMixin, TimestampMixin, Base):
    """Línea de una Purchase Order: SKU × esquema × cantidad × precio."""

    __tablename__ = "purchase_order_lines"

    po_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("purchase_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    scheme_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("schemes.code", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_ordered: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    qty_received: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("0")
    )
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    landed_cost_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    price_source: Mapped[str] = mapped_column(
        String(16),
        nullable=False,
        server_default=text("'manual'"),
    )

    purchase_order: Mapped[PurchaseOrder] = relationship(
        "PurchaseOrder",
        back_populates="lines",
        lazy="noload",
    )
    goods_receipts: Mapped[list[GoodsReceipt]] = relationship(
        "GoodsReceipt",
        back_populates="po_line",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("qty_ordered > 0", name="ck_pol_qty_ordered_pos"),
        CheckConstraint("qty_received >= 0", name="ck_pol_qty_received_nonneg"),
        CheckConstraint("unit_price >= 0", name="ck_pol_unit_price_nonneg"),
        CheckConstraint("price_source IN ('manual','pir')", name="ck_pol_price_source"),
        Index("idx_pol_po", "po_id"),
        Index("idx_pol_sku", "sku"),
    )


class GoodsReceipt(UuidPkMixin, TimestampMixin, Base):
    """Registro de recepción física de mercancía contra una línea de PO."""

    __tablename__ = "goods_receipts"

    po_line_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("purchase_order_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_received: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    received_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actual_unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    actual_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    map_before: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    map_after: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    fx_rate_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("fx_rates.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        server_default=text("'pending'"),
    )
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    po_line: Mapped[PurchaseOrderLine] = relationship(
        "PurchaseOrderLine",
        back_populates="goods_receipts",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint("qty_received > 0", name="ck_gr_qty_received_pos"),
        CheckConstraint(
            "status IN ('pending','processed','error')",
            name="ck_gr_status",
        ),
        Index("idx_gr_po_line", "po_line_id"),
        Index(
            "idx_gr_status_pending",
            "status",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("idx_gr_received_at", "received_at", postgresql_ops={"received_at": "DESC"}),
    )


class CostLot(UuidPkMixin, TimestampMixin, Base):
    """Lote de coste FIFO creado al procesar un Goods Receipt."""

    __tablename__ = "cost_lots"

    sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_code: Mapped[str] = mapped_column(String(64), nullable=False)
    scheme_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("schemes.code", ondelete="RESTRICT"),
        nullable=False,
    )
    gr_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("goods_receipts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_original: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    qty_remaining: Mapped[Decimal] = mapped_column(Numeric(12, 3), nullable=False)
    unit_cost_aed: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("qty_original > 0", name="ck_cl_qty_original_pos"),
        CheckConstraint("qty_remaining >= 0", name="ck_cl_qty_remaining_nonneg"),
        CheckConstraint("unit_cost_aed >= 0", name="ck_cl_unit_cost_nonneg"),
        CheckConstraint("qty_remaining <= qty_original", name="ck_cl_qty_remaining_lte_original"),
        Index("idx_cost_lots_lookup", "sku", "supplier_code", "scheme_code"),
        Index("idx_cost_lots_gr", "gr_id"),
    )


class ERPSyncEvent(UuidPkMixin, TimestampMixin, Base):
    """Outbox de eventos ERP salientes (US-INV-01-07).

    Patrón transactional outbox: el evento se inserta en la misma transacción
    que el GR — si la transacción hace rollback, el evento desaparece.
    """

    __tablename__ = "erp_sync_events"

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    adapter: Mapped[str] = mapped_column(String(32), nullable=False, server_default=text("'noop'"))
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    attempts: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(256), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','delivered','failed','skipped')",
            name="ck_erp_sync_status",
        ),
        Index(
            "idx_erp_sync_pending",
            "status",
            postgresql_where=text("status = 'pending'"),
        ),
        Index("idx_erp_sync_entity", "entity_id", "event_type"),
    )


class InventoryPosition(UuidPkMixin, TimestampMixin, Base):
    """Posición de inventario 5D: product × warehouse × location × lot × stock_type.

    `total_stock_value_aed` es una generated column de Postgres:
    GENERATED ALWAYS AS (qty_on_hand * map_aed) STORED.
    """

    __tablename__ = "inventory_positions"

    sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    supplier_code: Mapped[str] = mapped_column(String(64), nullable=False)
    scheme_code: Mapped[str] = mapped_column(
        String(32),
        ForeignKey("schemes.code", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_on_hand: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("0")
    )
    map_aed: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_stock_value_aed: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4),
        Computed("qty_on_hand * map_aed", persisted=True),
        nullable=True,
    )
    last_gr_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("goods_receipts.id", ondelete="SET NULL"),
        nullable=True,
    )
    last_updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # EP-ERP-02-02: columnas 5D
    warehouse_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        # FK a warehouses añadida en mig 108
        nullable=True,
    )
    lot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        # FK a inventory_lots añadida en mig 107
        nullable=True,
    )
    location_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        # FK a warehouse_locations añadida en mig 108
        nullable=True,
    )
    stock_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'unrestricted'"),
    )

    __table_args__ = (
        UniqueConstraint(
            "sku",
            "supplier_code",
            "scheme_code",
            name="uq_inventory_positions",
        ),
        CheckConstraint(
            "stock_type IN ('unrestricted','quality_inspection','restricted','in_transit')",
            name="ck_inv_pos_stock_type",
        ),
        Index("idx_inv_pos_sku", "sku"),
    )


# ---------------------------------------------------------------------------
# US-ERP-02-01: Movement Types catalog
# ---------------------------------------------------------------------------


class StockMovementType(Base):
    """Catálogo de tipos de movimiento SAP-MM (101, 261, 301, 551, 561…)."""

    __tablename__ = "stock_movement_types"

    id: Mapped[UUID] = mapped_column(
        UUID_PG, primary_key=True, server_default=text("gen_random_uuid()")
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    direction: Mapped[str] = mapped_column(Text, nullable=False)
    requires_reference: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    posts_accounting: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    # mig 144 — default reason code to carry onto movements of this type
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    movements: Mapped[list[StockMovement]] = relationship(
        "StockMovement",
        back_populates="movement_type",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "direction IN ('IN','OUT','TRANSFER')",
            name="ck_smt_direction",
        ),
    )


class StockMovement(Base):
    """Movimiento físico de stock — diario de entradas/salidas/traslados."""

    __tablename__ = "stock_movements"

    id: Mapped[UUID] = mapped_column(
        UUID_PG, primary_key=True, server_default=text("gen_random_uuid()")
    )
    movement_type_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("stock_movement_types.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    lot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        # FK real a inventory_lots añadida en mig 107
        nullable=True,
    )
    warehouse_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        # FK real a warehouses añadida en mig 108
        nullable=True,
    )
    location_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    reference_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    reference_type: Mapped[str | None] = mapped_column(Text, nullable=True)
    reversal_of: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("stock_movements.id", ondelete="SET NULL"),
        nullable=True,
    )
    # mig 144 — accounting link (no FK to avoid circular dep with journal_entries)
    accounting_document_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        nullable=True,
    )
    # mig 144 — reason code (e.g. 'SCRAP', 'DAMAGE', 'ADJUSTMENT')
    reason_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    posted_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    movement_type: Mapped[StockMovementType] = relationship(
        "StockMovementType",
        back_populates="movements",
        lazy="noload",
    )
    journal_entries: Mapped[list[JournalEntry]] = relationship(
        "JournalEntry",
        back_populates="source_movement",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint("qty <> 0", name="ck_sm_qty_nonzero"),
        CheckConstraint(
            "reference_type IN ('purchase_order','goods_receipt','sale_order') OR reference_type IS NULL",
            name="ck_sm_reference_type",
        ),
        Index("idx_sm_product", "product_sku"),
        Index("idx_sm_type", "movement_type_id"),
        Index("idx_sm_posted_at", "posted_at"),
        Index("idx_sm_reference", "reference_id", "reference_type"),
    )


class JournalEntry(Base):
    """Asiento contable simple creado cuando posts_accounting=true en el tipo de movimiento."""

    __tablename__ = "journal_entries"

    id: Mapped[UUID] = mapped_column(
        UUID_PG, primary_key=True, server_default=text("gen_random_uuid()")
    )
    source_movement_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("stock_movements.id", ondelete="CASCADE"),
        nullable=False,
    )
    debit_account: Mapped[str] = mapped_column(Text, nullable=False)
    credit_account: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default=text("'AED'"))
    posted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    source_movement: Mapped[StockMovement] = relationship(
        "StockMovement",
        back_populates="journal_entries",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_je_amount_pos"),
        Index("idx_je_movement", "source_movement_id"),
    )


# ---------------------------------------------------------------------------
# US-ERP-02-03: Lot tracking
# ---------------------------------------------------------------------------


class InventoryLot(Base):
    """Lote físico de inventario con trazabilidad upstream/downstream."""

    __tablename__ = "inventory_lots"

    id: Mapped[UUID] = mapped_column(
        UUID_PG, primary_key=True, server_default=text("gen_random_uuid()")
    )
    lot_number: Mapped[str] = mapped_column(Text, nullable=False)
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    manufacture_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    expiry_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    country_of_origin: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)
    quality_status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'released'")
    )
    po_line_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("purchase_order_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "quality_status IN ('released','hold','blocked')",
            name="ck_lot_quality_status",
        ),
        UniqueConstraint("lot_number", "product_sku", name="uq_lot_number_product"),
        Index("idx_lots_product", "product_sku"),
        Index("idx_lots_quality_status", "quality_status"),
    )


# ---------------------------------------------------------------------------
# US-ERP-02-04: Warehouse hierarchy
# ---------------------------------------------------------------------------


class Warehouse(UuidPkMixin, TimestampMixin, Base):
    """Almacén físico (nivel raíz de la jerarquía WH → Zone → Location)."""

    __tablename__ = "warehouses"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    # mig 146 — FEFO picking enabled for this warehouse (default true)
    fefo_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    zones: Mapped[list[WarehouseZone]] = relationship(
        "WarehouseZone",
        back_populates="warehouse",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (UniqueConstraint("code", name="uq_warehouse_code"),)


class WarehouseZone(UuidPkMixin, TimestampMixin, Base):
    """Zona dentro de un almacén (refrigerada, seca, peligrosa, general)."""

    __tablename__ = "warehouse_zones"

    warehouse_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    zone_type: Mapped[str | None] = mapped_column(Text, nullable=True)

    warehouse: Mapped[Warehouse] = relationship(
        "Warehouse",
        back_populates="zones",
        lazy="noload",
    )
    locations: Mapped[list[WarehouseLocation]] = relationship(
        "WarehouseLocation",
        back_populates="zone",
        lazy="noload",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "zone_type IN ('refrigerated','dry','hazardous','general') OR zone_type IS NULL",
            name="ck_zone_type",
        ),
        UniqueConstraint("warehouse_id", "code", name="uq_zone_wh_code"),
        Index("idx_zones_warehouse", "warehouse_id"),
    )


class WarehouseLocation(UuidPkMixin, TimestampMixin, Base):
    """Ubicación física (bin) dentro de una zona — formato WH1-A-03-02-B."""

    __tablename__ = "warehouse_locations"

    zone_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("warehouse_zones.id", ondelete="CASCADE"),
        nullable=False,
    )
    bin_code: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    max_weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)

    zone: Mapped[WarehouseZone] = relationship(
        "WarehouseZone",
        back_populates="locations",
        lazy="noload",
    )

    __table_args__ = (
        UniqueConstraint("zone_id", "bin_code", name="uq_location_zone_bin"),
        Index("idx_locations_zone", "zone_id"),
    )


# ---------------------------------------------------------------------------
# US-ERP-02-05: FEFO + expiry alerts
# ---------------------------------------------------------------------------


class ExpiryAlertThreshold(UuidPkMixin, TimestampMixin, Base):
    """Umbral de alerta de vencimiento configurable por producto (default 30 días)."""

    __tablename__ = "expiry_alert_thresholds"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    threshold_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("30"))

    __table_args__ = (Index("idx_eat_sku", "product_sku"),)


class InventoryAlert(UuidPkMixin, TimestampMixin, Base):
    """Alerta de inventario generada por jobs Celery (LOT_EXPIRY_WARNING, STOCKOUT, ROP_BREACH)."""

    __tablename__ = "inventory_alerts"

    alert_type: Mapped[str] = mapped_column(Text, nullable=False)
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    lot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("inventory_lots.id", ondelete="CASCADE"),
        nullable=True,
    )
    warehouse_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
    )
    severity: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'warning'"))
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, server_default=text("'{}'::jsonb"))
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('LOT_EXPIRY_WARNING','STOCKOUT','ROP_BREACH')",
            name="ck_inv_alert_type",
        ),
        CheckConstraint(
            "severity IN ('info','warning','critical')",
            name="ck_inv_alert_severity",
        ),
        Index("idx_inv_alerts_sku", "product_sku"),
        Index("idx_inv_alerts_type", "alert_type"),
        Index(
            "idx_inv_alerts_unresolved",
            "resolved_at",
            postgresql_where=text("resolved_at IS NULL"),
        ),
    )


# ---------------------------------------------------------------------------
# US-ERP-02-06: Replenishment params
# ---------------------------------------------------------------------------


class ReplenishmentParam(UuidPkMixin, TimestampMixin, Base):
    """Parámetros de reaprovisionamiento por producto × almacén (ROP / safety stock)."""

    __tablename__ = "replenishment_params"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    warehouse_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
    )
    reorder_point: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("0")
    )
    safety_stock: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("0")
    )
    reorder_qty: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("1")
    )
    lead_time_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("7"))
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        UniqueConstraint("product_sku", "warehouse_id", name="uq_replenishment_params_sku_wh"),
        CheckConstraint("reorder_point >= 0", name="ck_rp_reorder_point_nonneg"),
        CheckConstraint("safety_stock >= 0", name="ck_rp_safety_stock_nonneg"),
        CheckConstraint("reorder_qty > 0", name="ck_rp_reorder_qty_pos"),
        CheckConstraint("lead_time_days >= 0", name="ck_rp_lead_time_nonneg"),
        Index("idx_rp_sku", "product_sku"),
        Index("idx_rp_warehouse", "warehouse_id"),
        Index(
            "idx_rp_active",
            "is_active",
            postgresql_where=text("is_active = true"),
        ),
    )


# ---------------------------------------------------------------------------
# US-ERP-02-07: ABC classification + cycle count schedules
# ---------------------------------------------------------------------------


class ProductAbcClassification(UuidPkMixin, Base):
    """Clasificación ABC por valor de consumo anual (actualizada mensualmente)."""

    __tablename__ = "product_abc_classifications"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    warehouse_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
    )
    abc_class: Mapped[str] = mapped_column(Text, nullable=False)
    annual_consumption_value: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    pct_of_total: Mapped[Decimal] = mapped_column(
        Numeric(7, 4), nullable=False, server_default=text("0")
    )
    classified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("product_sku", "warehouse_id", name="uq_abc_sku_wh"),
        CheckConstraint("abc_class IN ('A','B','C')", name="ck_abc_class"),
        CheckConstraint("annual_consumption_value >= 0", name="ck_abc_value_nonneg"),
        CheckConstraint("pct_of_total >= 0 AND pct_of_total <= 100", name="ck_abc_pct_range"),
        Index("idx_abc_sku", "product_sku"),
        Index("idx_abc_warehouse", "warehouse_id"),
        Index("idx_abc_class", "abc_class"),
    )


class CycleCountSchedule(UuidPkMixin, TimestampMixin, Base):
    """Calendario de conteos cíclicos por clase ABC y almacén."""

    __tablename__ = "cycle_count_schedules"

    warehouse_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="CASCADE"),
        nullable=False,
    )
    abc_class: Mapped[str] = mapped_column(Text, nullable=False)
    frequency_days: Mapped[int] = mapped_column(Integer, nullable=False)
    next_count_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_count_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    __table_args__ = (
        CheckConstraint("abc_class IN ('A','B','C')", name="ck_ccs_abc_class"),
        CheckConstraint("frequency_days > 0", name="ck_ccs_frequency_pos"),
        Index("idx_ccs_warehouse", "warehouse_id"),
        Index(
            "idx_ccs_active",
            "is_active",
            postgresql_where=text("is_active = true"),
        ),
    )


# ---------------------------------------------------------------------------
# US-ERP-02-07: Cycle Count execution records (mig 137)
# ---------------------------------------------------------------------------


class CycleCount(UuidPkMixin, TimestampMixin, Base):
    """Registro de ejecución de un conteo cíclico por schedule × SKU × almacén.

    ``variance`` = counted_qty - system_qty, almacenado como columna regular
    (no GENERATED ALWAYS) para compatibilidad con PG < 12 y flexibilidad de ajuste.
    """

    __tablename__ = "cycle_counts"

    schedule_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("cycle_count_schedules.id", ondelete="CASCADE"),
        nullable=False,
    )
    location_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("warehouse_locations.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    warehouse_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=False,
    )
    scheduled_date: Mapped[date] = mapped_column(Date, nullable=False)
    # nullable until physically counted
    counted_qty: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    # snapshot of InventoryPosition.qty_on_hand at count time
    system_qty: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    # counted_qty - system_qty, maintained by application logic
    variance: Mapped[Decimal | None] = mapped_column(Numeric(15, 3), nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'scheduled'"))
    counted_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        # FK to auth.users — managed via Supabase Auth
        nullable=True,
    )
    approved_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        nullable=True,
    )
    counted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint(
            "status IN ('scheduled','in_progress','pending_approval','approved','rejected')",
            name="ck_cycle_counts_status",
        ),
        Index("ix_cc_schedule", "schedule_id"),
        Index("ix_cc_sku_wh", "product_sku", "warehouse_id", "scheduled_date"),
    )
