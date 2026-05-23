"""Billing & Facturación models — EP-ERP-05.

Modelos para el módulo de Facturación:
- Invoice / InvoiceLine (US-ERP-05-01)
- DunningLevel / DunningHistory (US-ERP-05-03)
- EInvoiceSubmission (US-ERP-05-04)
- PaymentPromise (US-ERP-05-05)
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
    from app.db.models.sales import SalesOrder, SalesOrderLine, OutboundDelivery
    from app.db.models.user import User


# ---------------------------------------------------------------------------
# US-ERP-05-01 — Invoice
# ---------------------------------------------------------------------------


class Invoice(UuidPkMixin, Base):
    """Cabecera de factura — STANDARD, CREDIT_MEMO, DEBIT_MEMO, PROFORMA, INTERCOMPANY."""

    __tablename__ = "invoices"

    invoice_number: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    invoice_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'STANDARD'"),
    )
    delivery_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("outbound_deliveries.id", ondelete="RESTRICT"),
        nullable=True,
    )
    so_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("sales_orders.id", ondelete="RESTRICT"),
        nullable=True,
    )
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    invoice_date: Mapped[date] = mapped_column(
        Date,
        nullable=False,
        server_default=text("CURRENT_DATE"),
    )
    due_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    subtotal: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tax_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default=text("0"),
    )
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    currency: Mapped[str] = mapped_column(
        CHAR(3),
        nullable=False,
        server_default=text("'AED'"),
    )
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'draft'"),
    )
    # Accounting document ref — FK añadida post-merge EP-ERP-06
    accounting_document_id: Mapped[UUID | None] = mapped_column(UUID_PG, nullable=True)
    # FK a la factura origen para notas de crédito y cancelaciones (mig 138)
    original_invoice_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("invoices.id", ondelete="SET NULL"),
        nullable=True,
    )
    payment_terms: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'NET30'"),
    )
    # FK a payment_terms catalog (mig 139) — nullable para retrocompatibilidad
    payment_terms_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("payment_terms.id", ondelete="SET NULL"),
        nullable=True,
    )
    # e-invoice compliance (US-ERP-05-04)
    e_invoice_status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'not_required'"),
    )
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
    lines: Mapped[list["InvoiceLine"]] = relationship(
        "InvoiceLine",
        back_populates="invoice",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    dunning_history: Mapped[list["DunningHistory"]] = relationship(
        "DunningHistory",
        back_populates="invoice",
        lazy="dynamic",
    )
    e_invoice_submissions: Mapped[list["EInvoiceSubmission"]] = relationship(
        "EInvoiceSubmission",
        back_populates="invoice",
        lazy="dynamic",
    )
    payment_promises: Mapped[list["PaymentPromise"]] = relationship(
        "PaymentPromise",
        back_populates="invoice",
        lazy="dynamic",
    )

    __table_args__ = (
        CheckConstraint(
            "invoice_type IN ('STANDARD','CREDIT_MEMO','DEBIT_MEMO','PROFORMA','INTERCOMPANY','CANCELLATION')",
            name="ck_invoice_type",
        ),
        CheckConstraint(
            "status IN ('draft','posted','cancelled','reversed')",
            name="ck_invoice_status",
        ),
        CheckConstraint(
            "e_invoice_status IN ('not_required','pending','compliant','rejected')",
            name="ck_invoice_e_invoice_status",
        ),
        Index("idx_invoice_customer_id", "customer_id"),
        Index("idx_invoice_status", "status"),
        Index("idx_invoice_so_id", "so_id"),
        Index("idx_invoice_delivery_id", "delivery_id"),
        Index("idx_invoice_due_date", "due_date"),
    )


class InvoiceLine(UuidPkMixin, Base):
    """Línea de factura — por SKU."""

    __tablename__ = "invoice_lines"

    invoice_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    so_line_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("sales_order_lines.id", ondelete="SET NULL"),
        nullable=True,
    )
    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="RESTRICT"),
        nullable=False,
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    qty: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(18, 4), nullable=False)
    discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0"),
    )
    tax_rate: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("5"),
    )
    line_total: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="lines")

    __table_args__ = (
        Index("idx_invoice_line_invoice_id", "invoice_id"),
        Index("idx_invoice_line_sku", "product_sku"),
    )


# ---------------------------------------------------------------------------
# US-ERP-05-03 — Dunning
# ---------------------------------------------------------------------------


class DunningLevel(UuidPkMixin, Base):
    """Configuración de niveles de morosidad."""

    __tablename__ = "dunning_levels"

    level: Mapped[int] = mapped_column(Integer, nullable=False, unique=True)
    days_overdue: Mapped[int] = mapped_column(Integer, nullable=False)
    action: Mapped[str] = mapped_column(Text, nullable=False)
    fee_amount: Mapped[Decimal] = mapped_column(
        Numeric(18, 4),
        nullable=False,
        server_default=text("0"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )

    __table_args__ = (
        CheckConstraint(
            "action IN ('reminder','warning','final_notice','legal')",
            name="ck_dunning_level_action",
        ),
    )


class DunningHistory(UuidPkMixin, Base):
    """Historial de acciones de dunning por invoice."""

    __tablename__ = "dunning_history"

    invoice_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    dunning_level: Mapped[int] = mapped_column(Integer, nullable=False)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="dunning_history")

    __table_args__ = (
        Index("idx_dunning_history_invoice_id", "invoice_id"),
        Index("idx_dunning_history_customer_id", "customer_id"),
    )


# ---------------------------------------------------------------------------
# US-ERP-05-04 — E-Invoice Submissions
# ---------------------------------------------------------------------------


class EInvoiceSubmission(UuidPkMixin, Base):
    """Registro de envío a sistemas de facturación electrónica (ZATCA, CFDI, etc)."""

    __tablename__ = "e_invoice_submissions"

    invoice_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    standard: Mapped[str] = mapped_column(Text, nullable=False)
    submission_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    response_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'pending'"),
    )
    xml_payload: Mapped[str | None] = mapped_column(Text, nullable=True)
    qr_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="e_invoice_submissions")

    __table_args__ = (
        CheckConstraint(
            "standard IN ('CFDI_4.0','ZATCA_PHASE2','UBL_2.1','PEPPOL')",
            name="ck_e_invoice_standard",
        ),
        CheckConstraint(
            "status IN ('pending','submitted','accepted','rejected','cancelled')",
            name="ck_e_invoice_status",
        ),
        Index("idx_e_invoice_invoice_id", "invoice_id"),
        Index("idx_e_invoice_status", "status"),
    )


# ---------------------------------------------------------------------------
# US-ERP-05-05 — Payment Promises
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# US-ERP-05-03 — Payment Terms catalog (mig 139)
# ---------------------------------------------------------------------------


class PaymentTerms(UuidPkMixin, Base):
    """Catálogo de condiciones de pago (NET30, NET60, 2/10 NET30, etc.)."""

    __tablename__ = "payment_terms"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    net_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("30"),
    )
    discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2),
        nullable=False,
        server_default=text("0"),
    )
    discount_days: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        server_default=text("0"),
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        server_default=text("true"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (Index("idx_payment_terms_code", "code"),)


class PaymentPromise(UuidPkMixin, Base):
    """Promesa de pago por cliente — seguimiento AR."""

    __tablename__ = "payment_promises"

    invoice_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("invoices.id", ondelete="CASCADE"),
        nullable=False,
    )
    customer_id: Mapped[str] = mapped_column(Text, nullable=False)
    promised_date: Mapped[date] = mapped_column(Date, nullable=False)
    promised_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 4), nullable=True)
    status: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'active'"),
    )
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

    # Relationships
    invoice: Mapped["Invoice"] = relationship("Invoice", back_populates="payment_promises")

    __table_args__ = (
        CheckConstraint(
            "status IN ('active','kept','broken','cancelled')",
            name="ck_payment_promise_status",
        ),
        Index("idx_payment_promise_invoice_id", "invoice_id"),
        Index("idx_payment_promise_customer_id", "customer_id"),
        Index("idx_payment_promise_promised_date", "promised_date"),
    )
