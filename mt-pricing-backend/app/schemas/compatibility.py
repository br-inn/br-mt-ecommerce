"""Pydantic V2 schemas para ProductCompatibility (Wave 7 — recambios M:N).

Convenciones:
- ``from_attributes=True`` en todos los response schemas.
- ConfigDict con ``extra="forbid"`` en schemas de request.
- ``CompatibilityKind`` es un Literal-enum para validación estricta en requests.
- ``ProductCompatibilityResponse`` incluye ``compatible_product`` desnormalizado
  para la UI (sku, name_en, family, primary_image_url opcional).
"""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CompatibilityKind(str, Enum):
    """Tipos de relación de compatibilidad entre productos."""

    spare_part = "spare_part"
    accessory = "accessory"
    replaces = "replaces"
    replaced_by = "replaced_by"
    compatible_with = "compatible_with"


# ---------------------------------------------------------------------------
# Embedded / denormalizado
# ---------------------------------------------------------------------------
class CompatibleProductSummary(BaseModel):
    """Resumen del producto destino — incluido en la respuesta para la UI."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sku: str
    name_en: str
    family: str
    primary_image_url: str | None = None


# ---------------------------------------------------------------------------
# Base / Create / Patch / Response
# ---------------------------------------------------------------------------
class ProductCompatibilityBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: CompatibilityKind
    notes: str | None = Field(default=None, max_length=1024)
    position: int = Field(default=0, ge=0, le=32767)


class ProductCompatibilityCreate(ProductCompatibilityBase):
    """Body para POST /products/{sku}/compatibility."""

    compatible_with_sku: str = Field(min_length=3, max_length=64)


class ProductCompatibilityPatch(BaseModel):
    """Body para PATCH individual (notas / posición)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    notes: str | None = Field(default=None, max_length=1024)
    position: int | None = Field(default=None, ge=0, le=32767)


class ProductCompatibilityReplaceItem(ProductCompatibilityBase):
    """Ítem dentro del body de PUT /products/{sku}/compatibility (bulk replace)."""

    compatible_with_sku: str = Field(min_length=3, max_length=64)


class ProductCompatibilityResponse(BaseModel):
    """Response de un enlace de compatibilidad."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    product_sku: str
    compatible_with_sku: str
    kind: CompatibilityKind
    notes: str | None = None
    position: int
    created_at: datetime
    created_by: UUID | None = None
    # Desnormalizado para UI: info básica del producto destino.
    compatible_product: CompatibleProductSummary | None = None
