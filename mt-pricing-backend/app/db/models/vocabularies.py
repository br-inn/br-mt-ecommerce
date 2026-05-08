"""ORM models — Certification, Application + M:N junction tables.

Wave 4 vocabularios: catálogos admin-curados con M:N a products.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class Certification(UuidPkMixin, Base):
    """Certificación homologada — catálogo curado por admin."""

    __tablename__ = "certifications"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    issued_by: Mapped[str | None] = mapped_column(Text, nullable=True)
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Reverse side — products that carry this certification.
    product_certifications: Mapped[list["ProductCertification"]] = relationship(
        back_populates="certification", cascade="all, delete-orphan"
    )


class Application(UuidPkMixin, Base):
    """Aplicación / uso de producto — catálogo curado por admin."""

    __tablename__ = "applications"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    # Reverse side — products that have this application.
    product_applications: Mapped[list["ProductApplication"]] = relationship(
        back_populates="application", cascade="all, delete-orphan"
    )


class ProductCertification(Base):
    """M:N junction: products ↔ certifications (con metadatos de certificado)."""

    __tablename__ = "product_certifications"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    certification_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("certifications.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    certificate_pdf_asset_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, nullable=True
    )
    obtained_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    certification: Mapped["Certification"] = relationship(
        back_populates="product_certifications"
    )
    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]
        "Product",
        back_populates="product_certifications",
    )

    __table_args__ = (
        Index("idx_product_certifications_cert", "certification_id"),
    )


class ProductApplication(Base):
    """M:N junction: products ↔ applications (con posición y flag primario)."""

    __tablename__ = "product_applications"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    application_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("applications.id", ondelete="RESTRICT"),
        primary_key=True,
        nullable=False,
    )
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    position: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default=text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    application: Mapped["Application"] = relationship(
        back_populates="product_applications"
    )
    product: Mapped["Product"] = relationship(  # type: ignore[name-defined]
        "Product",
        back_populates="product_applications",
    )

    __table_args__ = (
        Index("idx_product_applications_app", "application_id"),
        Index(
            "idx_product_applications_primary",
            "product_sku",
            postgresql_where=text("is_primary = true"),
        ),
    )
