"""Pydantic V2 schemas — Wave 6 (tablas técnicas estructuradas).

Cubre 3 ``kind`` con shapes diferentes en ``data jsonb``:
- ``materials_matrix``: matriz componente x material x observation.
- ``dimensions_by_dn``: rows por DN con columnas L/H/K/etc.
- ``pressure_temperature``: rows con (temp_c, pressure_max_bar).

Cada kind valida ``data`` con un sub-modelo Pydantic.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


TechTableKind = Literal["materials_matrix", "dimensions_by_dn", "pressure_temperature"]
TechTableSource = Literal["manual", "imported_pdf", "imported_excel"]


# ---------------------------------------------------------------------------
# Per-kind data schemas (validators for the ``data`` jsonb).
# ---------------------------------------------------------------------------
class MaterialsMatrixRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    component: str = Field(min_length=1, max_length=64)
    material: str = Field(min_length=1, max_length=128)
    observations: str | None = Field(default=None, max_length=512)


class MaterialsMatrixData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rows: list[MaterialsMatrixRow] = Field(default_factory=list, max_length=64)


class DimensionsByDnRow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dn: str = Field(min_length=1, max_length=16)
    # Cualquier dimensión nominal (L, H, K, T1, etc.) en mm — valor o None.
    measures: dict[str, float | None] = Field(default_factory=dict)


class DimensionsByDnData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    columns: list[str] = Field(default_factory=list, description="Ordered measure names")
    rows: list[DimensionsByDnRow] = Field(default_factory=list, max_length=64)

    @model_validator(mode="after")
    def _check_columns_consistency(self) -> "DimensionsByDnData":
        # Each row's measures keys should be a subset of columns when columns is provided.
        if self.columns:
            allowed = set(self.columns)
            for r in self.rows:
                unknown = set(r.measures) - allowed
                if unknown:
                    raise ValueError(f"row dn={r.dn!r} has unknown measure(s): {sorted(unknown)}")
        return self


class PressureTemperaturePoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    temp_c: int = Field(ge=-273, le=2000)
    pressure_max_bar: float = Field(ge=0, le=9999.99)


class PressureTemperatureData(BaseModel):
    model_config = ConfigDict(extra="forbid")
    points: list[PressureTemperaturePoint] = Field(default_factory=list, max_length=128)
    notes: str | None = Field(default=None, max_length=512)


# ---------------------------------------------------------------------------
# CRUD payloads
# ---------------------------------------------------------------------------
class ProductTechTableCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: TechTableKind
    schema_version: str = Field(default="v1", max_length=16)
    source: TechTableSource = "manual"
    data: dict[str, Any]
    source_asset_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=512)

    @model_validator(mode="after")
    def _validate_data_per_kind(self) -> "ProductTechTableCreate":
        try:
            if self.kind == "materials_matrix":
                MaterialsMatrixData.model_validate(self.data)
            elif self.kind == "dimensions_by_dn":
                DimensionsByDnData.model_validate(self.data)
            elif self.kind == "pressure_temperature":
                PressureTemperatureData.model_validate(self.data)
        except Exception as exc:  # re-raise as ValueError for Pydantic-level error
            raise ValueError(f"data invalid for kind={self.kind}: {exc}") from exc
        return self


class ProductTechTablePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: str | None = Field(default=None, max_length=16)
    source: TechTableSource | None = None
    data: dict[str, Any] | None = None
    source_asset_id: UUID | None = None
    notes: str | None = Field(default=None, max_length=512)


class ProductTechTableResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    product_sku: str
    kind: TechTableKind
    schema_version: str
    source: TechTableSource
    data: dict[str, Any]
    source_asset_id: UUID | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime
