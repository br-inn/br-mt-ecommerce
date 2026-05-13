"""Procurement models — EP-ERP-03.

Modelos para el módulo Compras P2P:
- PurchaseRequisition / ApprovalDecision (US-ERP-03-01)
- ApprovalRule (US-ERP-03-02)
- VendorProductCondition / PIR (US-ERP-03-03)
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import TYPE_CHECKING
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
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
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG

if TYPE_CHECKING:
    pass


class PurchaseRequisition(UuidPkMixin, Base):
    """Solicitud interna de compra — lifecycle: draft → pending_approval → approved/rejected."""

    __tablename__ = "purchase_requisitions"

    pr_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    requester_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    product_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("products.id", ondelete="SET NULL"),
        nullable=True,
    )
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    uom: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'UNIT'")
    )
    required_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cost_center_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    suggested_vendor_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    estimated_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(18, 4), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'draft'")
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    decisions: Mapped[list[ApprovalDecision]] = relationship(
        "ApprovalDecision",
        primaryjoin=(
            "and_(ApprovalDecision.document_id == PurchaseRequisition.id, "
            "ApprovalDecision.document_type == 'purchase_requisition')"
        ),
        foreign_keys="[ApprovalDecision.document_id]",
        lazy="noload",
        viewonly=True,
        order_by="ApprovalDecision.decided_at",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','pending_approval','approved','rejected','cancelled','converted_to_po')",
            name="ck_pr_status",
        ),
        CheckConstraint("qty > 0", name="ck_pr_qty_pos"),
        Index("idx_pr_requester", "requester_id"),
        Index(
            "idx_pr_status",
            "status",
            postgresql_where=text("status NOT IN ('cancelled','converted_to_po')"),
        ),
        Index(
            "idx_pr_product",
            "product_id",
            postgresql_where=text("product_id IS NOT NULL"),
        ),
    )


class ApprovalDecision(UuidPkMixin, Base):
    """Registro inmutable de decisión de aprobación.

    Tabla append-only: no UPDATE ni DELETE por diseño (trazabilidad de auditoría).
    """

    __tablename__ = "approval_decisions"

    document_id: Mapped[UUID] = mapped_column(UUID_PG, nullable=False)
    document_type: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'purchase_requisition'")
    )
    approver_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    decided_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('APPROVE','REJECT','ESCALATE')",
            name="ck_ad_action",
        ),
        Index("idx_ad_document", "document_id", "document_type"),
    )


class ApprovalRule(UuidPkMixin, Base):
    """Regla de enrutamiento de aprobaciones configurable."""

    __tablename__ = "approval_rules"

    document_type: Mapped[str] = mapped_column(
        String(64), nullable=False, server_default=text("'purchase_requisition'")
    )
    min_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4), nullable=False, server_default=text("0")
    )
    max_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    category_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    approver_role: Mapped[str | None] = mapped_column(String(32), nullable=True)
    approver_user_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    timeout_hours: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("48")
    )
    priority: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        Index(
            "idx_approval_rules_lookup",
            "document_type",
            "priority",
            "is_active",
            postgresql_where=text("is_active = true"),
        ),
    )


class VendorProductCondition(UuidPkMixin, Base):
    """Purchasing Info Record (PIR) — condiciones proveedor-producto."""

    __tablename__ = "vendor_product_conditions"

    vendor_id: Mapped[str] = mapped_column(String(64), nullable=False)
    product_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("products.id", ondelete="RESTRICT"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    uom: Mapped[str] = mapped_column(
        String(32), nullable=False, server_default=text("'UNIT'")
    )
    moq: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    lead_time_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_from: Mapped[date] = mapped_column(
        Date, nullable=False, server_default=text("CURRENT_DATE")
    )
    valid_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default=text("'AED'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("vendor_id", "product_id", "valid_from", name="uq_vpc_vendor_product_date"),
        CheckConstraint("price >= 0", name="ck_vpc_price_nonneg"),
        CheckConstraint("moq >= 1", name="ck_vpc_moq_pos"),
        Index(
            "idx_vpc_vendor_product",
            "vendor_id",
            "product_id",
            postgresql_where=text("is_active = true"),
        ),
        Index(
            "idx_vpc_validity",
            "valid_from",
            "valid_to",
            postgresql_where=text("is_active = true"),
        ),
    )
