"""Sales / O2C models — EP-ERP-04.

Modelos para el módulo Ventas Order-to-Cash:
- SalesOrder / SalesOrderLine (US-ERP-04-01)
- StockReservation / AtpCheckingRule (US-ERP-04-02)
- CustomerCreditLimit / CustomerOpenItem (US-ERP-04-03)
- OutboundDelivery / OutboundDeliveryLine (US-ERP-04-04)
- RmaHeader / RmaLine / CreditMemo (US-ERP-04-05)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    CHAR,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG

if TYPE_CHECKING:
    pass


# ---------------------------------------------------------------------------
# US-ERP-04-01 — Sales Orders
# ---------------------------------------------------------------------------


class SalesOrder(UuidPkMixin, Base):
    """Cabecera de Orden de Venta — lifecycle: draft → … → closed."""

    __tablename__ = "sales_orders"

    so_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    order_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'STANDARD'"),
    )
    quotation_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'draft'"),
    )
    warehouse_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
    )
    requested_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_terms: Mapped[str | None] = mapped_column(Text, nullable=True)
    currency: Mapped[str | None] = mapped_column(
        CHAR(3), nullable=True, server_default=text("'AED'")
    )
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    # Relationships
    lines: Mapped[list[SalesOrderLine]] = relationship(
        "SalesOrderLine",
        back_populates="order",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    deliveries: Mapped[list[OutboundDelivery]] = relationship(
        "OutboundDelivery",
        back_populates="order",
        lazy="dynamic",
    )
    open_items: Mapped[list[CustomerOpenItem]] = relationship(
        "CustomerOpenItem",
        back_populates="order",
        lazy="dynamic",
    )

    __table_args__ = (
        CheckConstraint(
            "order_type IN ('STANDARD','RUSH','CASH','CONTRACT_RELEASE','RETURN')",
            name="ck_so_order_type",
        ),
        CheckConstraint(
            "status IN ('draft','confirmed','in_fulfillment','partially_delivered','delivered','invoiced','closed','cancelled','on_credit_hold')",
            name="ck_so_status",
        ),
        Index("idx_so_customer_id", "customer_id"),
        Index("idx_so_status", "status"),
        Index("idx_so_created_at", "created_at"),
    )


class SalesOrderLine(UuidPkMixin, Base):
    """Línea de orden de venta — por SKU."""

    __tablename__ = "sales_order_lines"

    so_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("sales_orders.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    uom: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'UNIT'"))
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0"),
    )
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    confirmed_qty: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    requested_delivery_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'open'"),
    )

    # Relationships
    order: Mapped[SalesOrder] = relationship("SalesOrder", back_populates="lines")
    reservations: Mapped[list[StockReservation]] = relationship(
        "StockReservation",
        back_populates="so_line",
        lazy="dynamic",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('open','confirmed','partially_delivered','delivered','cancelled')",
            name="ck_sol_status",
        ),
        Index("idx_sol_so_id", "so_id"),
        Index("idx_sol_product_sku", "product_sku"),
    )


# ---------------------------------------------------------------------------
# US-ERP-04-02 — ATP + Reservations
# ---------------------------------------------------------------------------


class AtpCheckingRule(UuidPkMixin, Base):
    """Reglas de ATP por SKU (null = regla default)."""

    __tablename__ = "atp_checking_rules"

    product_sku: Mapped[str | None] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=True,
    )
    include_safety_stock: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    include_planned_receipts: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    include_qa_stock: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("false"),
    )
    horizon_days: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("30"))

    __table_args__ = (Index("idx_atp_rule_sku", "product_sku"),)


class StockReservation(UuidPkMixin, Base):
    """Soft reservation de stock para una línea SO."""

    __tablename__ = "stock_reservations"

    so_line_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("sales_order_lines.id", ondelete="CASCADE"),
        nullable=False,
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
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    reserved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )

    # Relationships
    so_line: Mapped[SalesOrderLine] = relationship("SalesOrderLine", back_populates="reservations")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','consumed','expired','cancelled')",
            name="ck_reservation_status",
        ),
        Index("idx_reservation_so_line", "so_line_id"),
        Index("idx_reservation_sku_status", "product_sku", "status"),
        Index("idx_reservation_warehouse", "warehouse_id"),
    )


# ---------------------------------------------------------------------------
# US-ERP-04-03 — Credit Management
# ---------------------------------------------------------------------------


class CustomerCreditLimit(UuidPkMixin, Base):
    """Límite de crédito por cliente."""

    __tablename__ = "customer_credit_limits"

    customer_id: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default=text("'AED'"))
    credit_horizon_days: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("30")
    )
    is_blocked: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    block_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    __table_args__ = (Index("idx_credit_limit_customer", "customer_id"),)


class CustomerOpenItem(UuidPkMixin, Base):
    """Partida abierta de cliente — SO o factura pendiente de cobro."""

    __tablename__ = "customer_open_items"

    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    so_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("sales_orders.id", ondelete="SET NULL"),
        nullable=True,
    )
    invoice_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    document_type: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'open'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    order: Mapped[SalesOrder | None] = relationship("SalesOrder", back_populates="open_items")

    __table_args__ = (
        CheckConstraint("document_type IN ('so','invoice')", name="ck_open_item_doc_type"),
        CheckConstraint("status IN ('open','partially_paid','paid')", name="ck_open_item_status"),
        Index("idx_open_items_customer", "customer_id"),
        Index("idx_open_items_so", "so_id"),
    )


# ---------------------------------------------------------------------------
# US-ERP-04-04 — Outbound Delivery
# ---------------------------------------------------------------------------


class OutboundDelivery(UuidPkMixin, Base):
    """Entrega de salida — cubre uno o varios SO lines."""

    __tablename__ = "outbound_deliveries"

    delivery_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    so_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("sales_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    warehouse_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="RESTRICT"),
        nullable=True,
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending_pick'"),
    )
    partial_delivery_allowed: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    order: Mapped[SalesOrder] = relationship("SalesOrder", back_populates="deliveries")
    lines: Mapped[list[OutboundDeliveryLine]] = relationship(
        "OutboundDeliveryLine",
        back_populates="delivery",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_pick','picking','packed','goods_issued','cancelled')",
            name="ck_delivery_status",
        ),
        Index("idx_delivery_so_id", "so_id"),
        Index("idx_delivery_status", "status"),
    )


class OutboundDeliveryLine(UuidPkMixin, Base):
    """Línea de entrega — mapea a una SO line."""

    __tablename__ = "outbound_delivery_lines"

    delivery_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("outbound_deliveries.id", ondelete="CASCADE"),
        nullable=False,
    )
    so_line_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("sales_order_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_planned: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    qty_picked: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default=text("0"),
    )
    lot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("inventory_lots.id", ondelete="SET NULL"),
        nullable=True,
    )
    location_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("warehouse_locations.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Relationships
    delivery: Mapped[OutboundDelivery] = relationship("OutboundDelivery", back_populates="lines")

    __table_args__ = (
        Index("idx_del_line_delivery", "delivery_id"),
        Index("idx_del_line_sku", "product_sku"),
    )


# ---------------------------------------------------------------------------
# US-ERP-04-05 — RMA + Credit Memo
# ---------------------------------------------------------------------------


class RmaHeader(UuidPkMixin, Base):
    """Return Merchandise Authorization — cabecera."""

    __tablename__ = "rma_headers"

    rma_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    original_so_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("sales_orders.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    return_type: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'requested'"),
    )
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    lines: Mapped[list[RmaLine]] = relationship(
        "RmaLine",
        back_populates="rma",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    credit_memos: Mapped[list[CreditMemo]] = relationship(
        "CreditMemo",
        back_populates="rma",
        lazy="dynamic",
    )
    return_deliveries: Mapped[list[ReturnDelivery]] = relationship(
        "ReturnDelivery",
        back_populates="rma",
        lazy="noload",
    )

    __table_args__ = (
        CheckConstraint(
            "return_type IN ('full','partial','damaged','wrong_item')",
            name="ck_rma_return_type",
        ),
        CheckConstraint(
            "status IN ('requested','approved','goods_received','credit_issued','closed','rejected')",
            name="ck_rma_status",
        ),
        Index("idx_rma_so_id", "original_so_id"),
        Index("idx_rma_customer", "customer_id"),
        Index("idx_rma_status", "status"),
    )


class RmaLine(UuidPkMixin, Base):
    """Línea de devolución."""

    __tablename__ = "rma_lines"

    rma_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("rma_headers.id", ondelete="CASCADE"),
        nullable=False,
    )
    so_line_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("sales_order_lines.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    qty_returned: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    lot_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("inventory_lots.id", ondelete="SET NULL"),
        nullable=True,
    )
    condition: Mapped[str] = mapped_column(Text, nullable=False)

    # Relationships
    rma: Mapped[RmaHeader] = relationship("RmaHeader", back_populates="lines")

    __table_args__ = (
        CheckConstraint(
            "condition IN ('resalable','damaged','to_dispose')",
            name="ck_rma_line_condition",
        ),
        Index("idx_rma_line_rma_id", "rma_id"),
        Index("idx_rma_line_sku", "product_sku"),
    )


class CreditMemo(UuidPkMixin, Base):
    """Nota de crédito generada automáticamente desde un RMA aprobado."""

    __tablename__ = "credit_memos"

    memo_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    rma_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("rma_headers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    currency: Mapped[str] = mapped_column(CHAR(3), nullable=False, server_default=text("'AED'"))
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    rma: Mapped[RmaHeader] = relationship("RmaHeader", back_populates="credit_memos")

    __table_args__ = (
        CheckConstraint(
            "status IN ('pending','approved','applied','cancelled')",
            name="ck_credit_memo_status",
        ),
        Index("idx_credit_memo_rma", "rma_id"),
        Index("idx_credit_memo_customer", "customer_id"),
    )


class ReturnDelivery(UuidPkMixin, Base):
    """Recepción física de devolución — VEN-18 (US-ERP-04-05).

    Registra quién recibió la mercancía, en qué almacén y cuándo.
    Se crea al confirmar la recepción de un RMA aprobado.
    """

    __tablename__ = "return_deliveries"

    rma_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("rma_headers.id", ondelete="RESTRICT"),
        nullable=False,
    )
    warehouse_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("warehouses.id", ondelete="SET NULL"),
        nullable=True,
    )
    received_date: Mapped[date] = mapped_column(Date, nullable=False)
    received_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    rma: Mapped[RmaHeader] = relationship("RmaHeader", back_populates="return_deliveries")

    __table_args__ = (Index("idx_return_delivery_rma", "rma_id"),)
