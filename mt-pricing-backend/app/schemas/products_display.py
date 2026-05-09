"""Pydantic V2 schemas — effective display + display pair (Wave 11 Stage 3).

Endpoints en ``app/api/routes/products_display.py``.
"""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CertificationRef(BaseModel):
    """Cert minimal para respuesta de effective display."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name: str
    issued_by: str | None = None
    scope: str | None = None
    logo_url: str | None = None


class EffectiveDisplayResponse(BaseModel):
    """Tags + certs efectivos: union dedup de serie defaults + product overrides."""

    model_config = ConfigDict(from_attributes=True)

    tags: list[str] = Field(default_factory=list)
    certifications: list[CertificationRef] = Field(default_factory=list)


class DisplayPairSetRequest(BaseModel):
    """Payload para enlazar este SKU a su pareja de display (color sibling)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    paired_sku: str = Field(min_length=1, max_length=64)
