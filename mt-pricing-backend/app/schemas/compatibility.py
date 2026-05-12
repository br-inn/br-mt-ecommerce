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

from pydantic import BaseModel, ConfigDict, Field, model_validator


class CompatibilityKind(str, Enum):
    """Tipos de relación de compatibilidad entre productos."""

    spare_part = "spare_part"
    accessory = "accessory"
    replaces = "replaces"
    replaced_by = "replaced_by"
    compatible_with = "compatible_with"


class CompatibilityOwnerType(str, Enum):
    """Tipo de owner polymorphic (Fase 5).

    - ``product`` (default): vínculo a un SKU concreto.
    - ``variant``: vínculo a una variante (futuro).
    - ``series``: vínculo a una serie entera, normalmente combinado con
      ``dn_min``/``dn_max`` para acotar el rango de calibres.
    """

    product = "product"
    variant = "variant"
    series = "series"


# ---------------------------------------------------------------------------
# Embedded / denormalizado
# ---------------------------------------------------------------------------
class CompatibleProductSummary(BaseModel):
    """Resumen del producto destino — incluido en la respuesta para la UI.

    Fase B (mig 065): name_en ahora opcional (viene de hybrid_property que lee
    de product_translations(en); puede ser None si la traducción no existe).
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sku: str
    name_en: str | None = None
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
    # Fase 5 — polymorphic owner. Default 'product' preserva compat con clientes
    # legacy que no envían el campo.
    owner_type: CompatibilityOwnerType = Field(default=CompatibilityOwnerType.product)
    # Fase 5 — rango de DN. Si ambos NULL aplica a cualquier calibre.
    dn_min: int | None = Field(default=None, ge=0, le=10000)
    dn_max: int | None = Field(default=None, ge=0, le=10000)

    @model_validator(mode="after")
    def _validate_dn_range(self) -> "ProductCompatibilityBase":
        if self.dn_min is not None and self.dn_max is not None:
            if self.dn_max < self.dn_min:
                raise ValueError("dn_max debe ser >= dn_min")
        return self


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
    # Fase 5 — polymorphic owner + DN range.
    owner_type: CompatibilityOwnerType = CompatibilityOwnerType.product
    dn_min: int | None = None
    dn_max: int | None = None
    created_at: datetime
    created_by: UUID | None = None
    # Desnormalizado para UI: info básica del producto destino.
    compatible_product: CompatibleProductSummary | None = None
