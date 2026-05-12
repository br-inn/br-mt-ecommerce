"""Pydantic V2 schemas — Fase 3 tablas técnicas granulares (PDF §9).

Convenciones (alineadas con schemas/attributes.py):
- ``ConfigDict(from_attributes=True)`` en Response models (ORM).
- ``ConfigDict(extra='forbid', str_strip_whitespace=True)`` en Create/Patch.
- Validators enforce: ``DimensionCell`` requiere value_number XOR value_text;
  ``PressureTemperaturePoint`` exige temperature_c y pressure_max_bar.

Tipos cubiertos:
- ActuationCodeResponse (read-only — catálogo curado por migración)
- StandardResponse / Create / Patch
- DimensionColumnCreate / Patch / Response
- DimensionRowCreate / Patch / Response (with nested cells)
- DimensionCellCreate / Patch / Response
- PressureTemperaturePointCreate / Patch / Response
- DimensionTableResponse — composite para render frontend (columns + rows
  con cells anidadas).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Patrones reutilizados
# ---------------------------------------------------------------------------
_CODE_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$"
_STANDARD_CODE_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9 _./-]{0,63}$"

ActuationType = Literal[
    "free_shaft", "handle", "gearbox", "motorized", "pneumatic"
]


# ===========================================================================
# ActuationCode (read-only)
# ===========================================================================
class ActuationCodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    name_en: str
    type: ActuationType
    created_at: datetime


# ===========================================================================
# Standard
# ===========================================================================
class StandardBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=_STANDARD_CODE_PATTERN,
        description="Standard code, e.g. 'ASTM A105' or 'EN 10204'.",
    )
    edition: str = Field(
        default="",
        max_length=32,
        description="Optional edition / year. Empty string when not specified.",
    )
    title_en: str = Field(min_length=1, max_length=512)
    reference_url: str | None = Field(default=None, max_length=1024)


class StandardCreate(StandardBase):
    pass


class StandardPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str | None = Field(
        default=None,
        min_length=1,
        max_length=64,
        pattern=_STANDARD_CODE_PATTERN,
    )
    edition: str | None = Field(default=None, max_length=32)
    title_en: str | None = Field(default=None, min_length=1, max_length=512)
    reference_url: str | None = Field(default=None, max_length=1024)


class StandardResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    edition: str
    title_en: str
    reference_url: str | None
    created_at: datetime


# ===========================================================================
# DimensionColumn
# ===========================================================================
class DimensionColumnBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=64, pattern=_CODE_PATTERN)
    label_en: str = Field(min_length=1, max_length=256)
    unit: str | None = Field(default=None, max_length=32)
    order_index: int = Field(default=0, ge=0, le=32767)


class DimensionColumnCreate(DimensionColumnBase):
    pass


class DimensionColumnPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label_en: str | None = Field(default=None, min_length=1, max_length=256)
    unit: str | None = Field(default=None, max_length=32)
    order_index: int | None = Field(default=None, ge=0, le=32767)


class DimensionColumnResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    family_id: UUID
    code: str
    label_en: str
    unit: str | None
    order_index: int


# ===========================================================================
# DimensionCell
# ===========================================================================
class DimensionCellBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    column_id: UUID
    value_number: Decimal | None = None
    value_text: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def _require_one_value(self) -> DimensionCellBase:
        has_number = self.value_number is not None
        has_text = self.value_text is not None and self.value_text != ""
        if not (has_number or has_text):
            raise ValueError(
                "DimensionCell requires value_number or value_text to be set."
            )
        return self


class DimensionCellCreate(DimensionCellBase):
    pass


class DimensionCellPatch(BaseModel):
    """Patch payload — values only (column_id immutable)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    value_number: Decimal | None = None
    value_text: str | None = Field(default=None, max_length=2048)

    @model_validator(mode="after")
    def _at_least_one(self) -> DimensionCellPatch:
        if self.value_number is None and (
            self.value_text is None or self.value_text == ""
        ):
            raise ValueError(
                "DimensionCell patch requires value_number or value_text."
            )
        return self


class DimensionCellResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    row_id: UUID
    column_id: UUID
    value_number: Decimal | None
    value_text: str | None


# ===========================================================================
# DimensionRow
# ===========================================================================
class DimensionRowBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    size_label: str | None = Field(default=None, max_length=64)
    dn: int | None = Field(default=None, ge=0, le=100_000)
    actuation_code_id: UUID | None = None
    order_index: int = Field(default=0, ge=0, le=32767)


class DimensionRowCreate(DimensionRowBase):
    """Optionally include cells inline for bulk creation."""

    cells: list[DimensionCellCreate] = Field(default_factory=list)


class DimensionRowPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    size_label: str | None = Field(default=None, max_length=64)
    dn: int | None = Field(default=None, ge=0, le=100_000)
    actuation_code_id: UUID | None = None
    order_index: int | None = Field(default=None, ge=0, le=32767)


class DimensionRowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_sku: str
    size_label: str | None
    dn: int | None
    actuation_code_id: UUID | None
    order_index: int
    created_at: datetime


class DimensionRowWithCells(DimensionRowResponse):
    """Row enriched with its cells — used by composite table response."""

    cells: list[DimensionCellResponse] = Field(default_factory=list)


# ===========================================================================
# Composite — DimensionTableResponse
# ===========================================================================
class DimensionTableResponse(BaseModel):
    """Full dimension table for a product (columns × rows × cells)."""

    model_config = ConfigDict(from_attributes=False)

    product_sku: str
    family_id: UUID | None
    columns: list[DimensionColumnResponse]
    rows: list[DimensionRowWithCells]


# ===========================================================================
# PressureTemperaturePoint
# ===========================================================================
class PressureTemperaturePointBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    series_variant_code: str | None = Field(default=None, max_length=64)
    temperature_c: Decimal = Field(
        description="Temperature in degrees Celsius."
    )
    pressure_max_bar: Decimal = Field(
        ge=Decimal("0"),
        description="Maximum allowed pressure in bar (non-negative).",
    )
    condition_en: str | None = Field(default=None, max_length=512)
    order_index: int = Field(default=0, ge=0, le=32767)


class PressureTemperaturePointCreate(PressureTemperaturePointBase):
    pass


class PressureTemperaturePointPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    series_variant_code: str | None = Field(default=None, max_length=64)
    temperature_c: Decimal | None = None
    pressure_max_bar: Decimal | None = Field(default=None, ge=Decimal("0"))
    condition_en: str | None = Field(default=None, max_length=512)
    order_index: int | None = Field(default=None, ge=0, le=32767)


class PressureTemperaturePointResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_sku: str
    series_variant_code: str | None
    temperature_c: Decimal
    pressure_max_bar: Decimal
    condition_en: str | None
    order_index: int
    created_at: datetime


class PressureTemperatureCurveResponse(BaseModel):
    """Composite curve grouped by series_variant_code (None bucket = default)."""

    model_config = ConfigDict(from_attributes=False)

    product_sku: str
    series_variant_code: str | None
    points: list[PressureTemperaturePointResponse]
