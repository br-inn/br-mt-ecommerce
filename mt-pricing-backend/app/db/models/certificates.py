"""ORM — certificates (documentos de certificación emitidos con lifecycle).

Diferencia clave con 'certifications':
  certifications = catálogo de conceptos curados por admin (ACS, WRAS, PZH…)
  certificates   = documento real emitido (nº 23 ACC LY 482, exp 11/07/2028)

Un Certificate tiene owner model_id (nivel modelo/serie). Los SKUs/DN que
cubre se detallan en certificate_scopes.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class Certificate(UuidPkMixin, Base):
    """Certificado emitido con número, fechas, estado lifecycle."""

    __tablename__ = "certificates"

    model_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("product_models.id", ondelete="SET NULL"), nullable=True
    )
    certification_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("certifications.id", ondelete="RESTRICT"), nullable=True
    )
    cert_number: Mapped[str] = mapped_column(Text, nullable=False)
    issuer: Mapped[str | None] = mapped_column(Text, nullable=True)
    issued_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    expires_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'valid'"))
    signatory_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    signatory_role: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    scopes: Mapped[list[CertificateScope]] = relationship(
        back_populates="certificate", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('valid','expiring_soon','critical','expired','renewing')",
            name="ck_certificate_status",
        ),
        Index("idx_certificates_model", "model_id"),
        Index("idx_certificates_certification", "certification_id"),
        Index("idx_certificates_status", "status"),
        Index("idx_certificates_expires", "expires_at"),
    )


class CertificateScope(UuidPkMixin, Base):
    """SKU o rango de DN cubierto por un certificado."""

    __tablename__ = "certificate_scopes"

    certificate_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("certificates.id", ondelete="CASCADE"), nullable=False
    )
    sku: Mapped[str | None] = mapped_column(
        Text, ForeignKey("products.sku", ondelete="CASCADE"), nullable=True
    )
    dn_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dn_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

    certificate: Mapped[Certificate] = relationship(back_populates="scopes")

    __table_args__ = (
        CheckConstraint(
            "dn_min IS NULL OR dn_max IS NULL OR dn_max >= dn_min",
            name="ck_cert_scope_dn",
        ),
        Index("idx_cert_scopes_cert", "certificate_id"),
        Index("idx_cert_scopes_sku", "sku"),
    )
