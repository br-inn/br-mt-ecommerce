"""Inventory costing models — EP-INV-01 (US-INV-01-01).

Tablas del pipeline Purchase Order → Goods Receipt → MAP automático.
Siguiendo el estándar SAP MM / NetSuite para distribuidoras.

No contiene lógica de negocio — el MAP Engine (US-INV-01-02) escribe en
estas tablas. Los valores `landed_cost_breakdown` y `actual_breakdown`
siguen la convención `*_aed` / `*_eur` / `*_pct` de `costs.breakdown`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    Index,
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


class PurchaseOrder(UuidPkMixin, TimestampMixin, Base):
    """Orden de compra emitida a un proveedor."""

    __tablename__ = "purchase_orders"

    po_number: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True
    )
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
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
        Index("idx_po_supplier", "supplier_code", "status"),
        Index(
            "idx_po_status",
            "status",
            postgresql_where=text(
                "status NOT IN ('received','cancelled')"
            ),
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
    qty_ordered: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    qty_received: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False, server_default=text("0")
    )
    unit_price: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    landed_cost_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
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
    qty_received: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    received_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    actual_unit_price: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    actual_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    map_before: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    map_after: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
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
    processed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

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
    qty_original: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    qty_remaining: Mapped[Decimal] = mapped_column(
        Numeric(12, 3), nullable=False
    )
    unit_cost_aed: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False
    )
    effective_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint("qty_original > 0", name="ck_cl_qty_original_pos"),
        CheckConstraint("qty_remaining >= 0", name="ck_cl_qty_remaining_nonneg"),
        CheckConstraint("unit_cost_aed >= 0", name="ck_cl_unit_cost_nonneg"),
        CheckConstraint(
            "qty_remaining <= qty_original", name="ck_cl_qty_remaining_lte_original"
        ),
        Index("idx_cost_lots_lookup", "sku", "supplier_code", "scheme_code"),
        Index("idx_cost_lots_gr", "gr_id"),
    )


class ERPSyncEvent(UuidPkMixin, TimestampMixin, Base):
    """Outbox de eventos ERP salientes (US-INV-01-07).

    Cada fila representa un evento (GR, MAP update, etc.) pendiente de envío
    al ERP externo. La Celery task ``mt.erp.push_erp_event`` consume estas
    filas y actualiza su ``status``.

    Patrón transactional outbox: el evento se inserta en la misma transacción
    que el GR — si la transacción hace rollback, el evento desaparece y no
    se intentará enviar.
    """

    __tablename__ = "erp_sync_events"

    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    adapter: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'noop'")
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'pending'")
    )
    attempts: Mapped[int] = mapped_column(nullable=False, server_default=text("0"))
    last_attempted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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
    """Posición de inventario agregada por (SKU × proveedor × esquema).

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
    map_aed: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
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
    last_updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint(
            "sku", "supplier_code", "scheme_code",
            name="uq_inventory_positions",
        ),
        Index("idx_inv_pos_sku", "sku"),
    )
