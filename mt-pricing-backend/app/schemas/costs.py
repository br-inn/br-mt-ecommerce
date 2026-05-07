"""Pydantic schemas para `costs` — US-1A-04-02 / US-1A-04-03 motor de costes.

Schema NUEVO (motor de costes versionado con FX as-of por trigger). El antiguo
schema (Wave 2A) se mantenía con campos `product_sku`, `total`, `currency`,
`valid_from`, `valid_to`. Aquí migramos a:

- ``sku``                 (FK products.sku)
- ``scheme_code``         (FK schemes.code)
- ``supplier_code``       (FK suppliers.code, opcional)
- ``currency_origin``     (FK currencies.code, default 'AED')
- ``effective_at``        (TIMESTAMPTZ, mandatory)
- ``breakdown``           (JSONB con convención `*_aed`/`*_eur`/`*_pct`)
- ``status``              ('active'|'superseded')
- ``fx_inferred``         (bool, importer)
- ``version``             (int, server-managed)
- ``scheme_landed_aed``   (Numeric(14,4), calculado por trigger)
- ``fx_rate_id``          (UUID, autopoblado por trigger)

Para compatibilidad con consumidores S2 (frontend `useCosts`) los aliases
legacy `product_sku`, `total`, `currency`, `valid_from`, `valid_to`, `fx_at`
siguen exponiéndose en `CostResponse`.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

CURRENCY_CODE_REGEX = r"^[A-Z]{3}$"
SCHEME_CODE_REGEX = r"^[A-Z][A-Z0-9_]{1,31}$"

SchemeCodeStr = Annotated[
    str,
    StringConstraints(min_length=2, max_length=32, pattern=SCHEME_CODE_REGEX),
]
CurrencyStr = Annotated[
    str,
    StringConstraints(min_length=3, max_length=3, pattern=CURRENCY_CODE_REGEX),
]
SkuStr = Annotated[
    str,
    StringConstraints(min_length=1, max_length=128),
]
SupplierStr = Annotated[
    str,
    StringConstraints(min_length=1, max_length=64),
]


# ---------------------------------------------------------------------------
# Cost — request payloads (NUEVO motor)
# ---------------------------------------------------------------------------
class CostCreate(BaseModel):
    """POST /costs — payload del Comercial.

    El backend:
      1. Valida `breakdown` contra `cost_components_template` del scheme.
      2. Inserta — el trigger `costs_stamp_fx_trg` busca FX as-of vía
         `fx_rate_at(currency_origin, 'AED', effective_at)` y estampa
         `fx_rate_id`. Si no encuentra rate → falla con
         `error.code='fx_rate_not_found_at_effective_at'`.
      3. El trigger AFTER suma `breakdown × FX` → `scheme_landed_aed`.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    sku: SkuStr
    scheme_code: SchemeCodeStr
    supplier_code: SupplierStr | None = None
    currency_origin: CurrencyStr = "AED"
    effective_at: datetime
    breakdown: dict[str, Any] = Field(default_factory=dict)
    fx_rate_id: UUID | None = None  # importer puede pasar explícito (preserva)
    fx_inferred: bool = False


class CostUpdate(BaseModel):
    """PUT /costs/{id} — versionado. Crea row nueva con version+1, marca la
    anterior `superseded`. Sólo el `breakdown` y `effective_at` viajan.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    breakdown: dict[str, Any] | None = None
    effective_at: datetime | None = None
    currency_origin: CurrencyStr | None = None
    fx_rate_id: UUID | None = None
    fx_inferred: bool | None = None

    @model_validator(mode="after")
    def _at_least_one(self) -> "CostUpdate":
        if not any(
            [
                self.breakdown is not None,
                self.effective_at is not None,
                self.currency_origin is not None,
                self.fx_rate_id is not None,
                self.fx_inferred is not None,
            ]
        ):
            raise ValueError("at least one field required for update")
        return self


# ---------------------------------------------------------------------------
# Compat: legacy CostBase / CostPatch — used by old API. Mantenemos el shape
# para no romper consumidores S2 mientras el frontend migra.
# ---------------------------------------------------------------------------
class CostBase(BaseModel):
    """[LEGACY] — fields del POST viejo. Conservado por compat con el cliente
    Wave 2A; el `create_cost` legacy mapea estos campos al schema nuevo.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scheme_code: SchemeCodeStr
    supplier_code: SupplierStr | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    total: Decimal | None = Field(default=None, ge=0)
    currency: CurrencyStr = "AED"
    valid_from: datetime | None = None
    valid_to: datetime | None = None


class CostPatch(BaseModel):
    """[LEGACY] PATCH parcial."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    scheme_code: SchemeCodeStr | None = None
    supplier_code: SupplierStr | None = None
    breakdown: dict[str, Any] | None = None
    total: Decimal | None = Field(default=None, ge=0)
    currency: CurrencyStr | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None


# ---------------------------------------------------------------------------
# Response schema
# ---------------------------------------------------------------------------
class CostResponse(BaseModel):
    """Response — incluye campos NUEVOS (sku, currency_origin, effective_at,
    status, version, fx_inferred, scheme_landed_aed) + ALIASES legacy
    (product_sku, currency, total, valid_from, valid_to, fx_at) para que el
    cliente S2 siga funcionando hasta que migre.
    """

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    # Nuevos (canónicos)
    sku: str
    scheme_code: str
    supplier_code: str | None = None
    currency_origin: str
    fx_rate_id: UUID | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    scheme_landed_aed: Decimal | None = None
    effective_at: datetime
    status: Literal["active", "superseded"]
    fx_inferred: bool = False
    version: int = 1
    created_by: UUID | None = None
    updated_by: UUID | None = None
    created_at: datetime
    updated_at: datetime
    # Legacy aliases (read-only) — provistos por hybrid_property en el modelo.
    product_sku: str | None = None
    currency: str | None = None
    total: Decimal | None = None
    valid_from: datetime | None = None
    valid_to: datetime | None = None
    fx_at: datetime | None = None


class CostMissingSkuItem(BaseModel):
    """Item de la respuesta `/products?missing_cost_scheme=FBA` — un SKU que
    no tiene cost activo para ese scheme.
    """

    model_config = ConfigDict(from_attributes=True)

    sku: str
    name: str | None = None


class CostBreakdownValidationWarning(BaseModel):
    """Warning emitido cuando `breakdown` trae claves no declaradas en el
    template del scheme. NO bloquea (BR-1a-03).
    """

    code: str = "unknown_breakdown_field"
    field: str


class CostCreatedResponse(BaseModel):
    """201 response — incluye warnings opcionales del breakdown validator."""

    cost: CostResponse
    warnings: list[CostBreakdownValidationWarning] = Field(default_factory=list)


__all__ = [
    "CostBase",
    "CostBreakdownValidationWarning",
    "CostCreate",
    "CostCreatedResponse",
    "CostMissingSkuItem",
    "CostPatch",
    "CostResponse",
    "CostUpdate",
]
