"""Pydantic V2 schemas — Certifications, Applications, Product vocabulary links.

Wave 4: vocabularios M:N para products.
Convenciones: Pydantic v2 ConfigDict, from_attributes=True para ORM.
"""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Certification
# ---------------------------------------------------------------------------
class CertificationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=32, description="Código único, e.g. 'CE', 'WRAS'.")
    name: str = Field(min_length=1, max_length=256)
    issued_by: str | None = Field(default=None, max_length=256)
    scope: str | None = Field(default=None, max_length=512)
    logo_url: str | None = Field(default=None, max_length=1024)
    active: bool = True


class CertificationCreate(CertificationBase):
    pass


class CertificationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    issued_by: str | None = None
    scope: str | None = None
    logo_url: str | None = None
    active: bool | None = None


class CertificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    issued_by: str | None
    scope: str | None
    logo_url: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------
class ApplicationBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=64, description="Código único, e.g. 'water', 'gas'.")
    name: str = Field(min_length=1, max_length=256)
    description: str | None = Field(default=None, max_length=1024)
    active: bool = True


class ApplicationCreate(ApplicationBase):
    pass


class ApplicationPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    description: str | None = None
    active: bool | None = None


class ApplicationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    description: str | None
    active: bool
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# Product ↔ Certification link
# ---------------------------------------------------------------------------
class ProductCertificationLink(BaseModel):
    """Payload para enlazar un producto a una certificación."""

    model_config = ConfigDict(extra="forbid")

    certification_id: UUID
    certificate_pdf_asset_id: UUID | None = None
    obtained_at: date | None = None
    expires_at: date | None = None
    notes: str | None = Field(default=None, max_length=1024)


class ProductCertificationResponse(BaseModel):
    """Respuesta desnormalizada: datos de la cert + metadatos del link."""

    model_config = ConfigDict(from_attributes=True)

    # Cert details
    certification_id: UUID
    code: str
    name: str
    issued_by: str | None
    scope: str | None
    logo_url: str | None

    # Link metadata
    certificate_pdf_asset_id: UUID | None
    obtained_at: date | None
    expires_at: date | None
    notes: str | None
    created_at: datetime

    @classmethod
    def from_link(cls, link: object) -> "ProductCertificationResponse":
        """Construir desde un row ProductCertification (con cert eager-loaded)."""
        cert = link.certification  # type: ignore[attr-defined]
        return cls(
            certification_id=link.certification_id,  # type: ignore[attr-defined]
            code=cert.code,
            name=cert.name,
            issued_by=cert.issued_by,
            scope=cert.scope,
            logo_url=cert.logo_url,
            certificate_pdf_asset_id=link.certificate_pdf_asset_id,  # type: ignore[attr-defined]
            obtained_at=link.obtained_at,  # type: ignore[attr-defined]
            expires_at=link.expires_at,  # type: ignore[attr-defined]
            notes=link.notes,  # type: ignore[attr-defined]
            created_at=link.created_at,  # type: ignore[attr-defined]
        )


# ---------------------------------------------------------------------------
# Product ↔ Application link
# ---------------------------------------------------------------------------
class ProductApplicationLink(BaseModel):
    """Payload para enlazar un producto a una aplicación."""

    model_config = ConfigDict(extra="forbid")

    application_id: UUID
    is_primary: bool = False
    position: int = Field(default=0, ge=0, le=32767)


class ProductApplicationResponse(BaseModel):
    """Respuesta desnormalizada: datos de la app + metadatos del link."""

    model_config = ConfigDict(from_attributes=True)

    # App details
    application_id: UUID
    code: str
    name: str
    description: str | None

    # Link metadata
    is_primary: bool
    position: int
    created_at: datetime

    @classmethod
    def from_link(cls, link: object) -> "ProductApplicationResponse":
        """Construir desde un row ProductApplication (con application eager-loaded)."""
        app = link.application  # type: ignore[attr-defined]
        return cls(
            application_id=link.application_id,  # type: ignore[attr-defined]
            code=app.code,
            name=app.name,
            description=app.description,
            is_primary=link.is_primary,  # type: ignore[attr-defined]
            position=link.position,  # type: ignore[attr-defined]
            created_at=link.created_at,  # type: ignore[attr-defined]
        )
