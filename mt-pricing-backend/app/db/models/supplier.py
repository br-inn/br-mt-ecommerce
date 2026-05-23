"""Supplier — proveedor con moneda contractual + lead time (US-1A-03-01).

Spec: `mt-sqlalchemy-models.md` §7.3. PK `code` TEXT (alineado con `products.sku`).
`contract_currency` FK→`currencies.code` (la tabla `currencies` se siembra en
la misma migración 0004 — ver `2026050X_create_currencies_and_suppliers.py`).

Soft-delete pattern: la tabla NO debe permitir DELETE en API (BR-1a-07 / NFR-35
VAT-compliance). El bloqueo a nivel BD se aplica por trigger en migration aparte
si se decide replicar el patrón de `products`. En S2 sólo se establece `active=false`
desde el service layer (US-1A-03-02).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Supplier(Base):
    __tablename__ = "suppliers"

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    contact_email: Mapped[str | None] = mapped_column(CITEXT)
    contact_phone: Mapped[str | None] = mapped_column(Text)

    # Moneda contractual — FK a currencies (seeded en misma migration).
    contract_currency: Mapped[str] = mapped_column(
        String(3),
        ForeignKey("currencies.code", ondelete="RESTRICT"),
        nullable=False,
    )

    lead_time_days: Mapped[int | None] = mapped_column(Integer)
    payment_terms: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    __table_args__ = (
        Index(
            "idx_suppliers_active",
            "active",
            postgresql_where=text("active = true"),
        ),
        Index("idx_suppliers_currency", "contract_currency"),
    )
