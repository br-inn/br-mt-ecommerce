"""Pydantic schemas para los endpoints `/imports/*` (US-1A-06-01)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImportApplyRequest(BaseModel):
    """Body opcional para `POST /imports/{run_id}/apply`."""

    model_config = ConfigDict(extra="forbid")

    chunk_size: int = Field(default=1000, ge=1, le=5000)
    # Stage 3 (Wave 11) — override de divisiones a asignar por SKU del run.
    # Si vacío, cae al `settings.PIM_DEFAULT_DIVISIONS` configurado.
    division_codes: list[str] | None = Field(default=None)


class ImportRunSummary(BaseModel):
    """Vista resumida de un run (sin samples)."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    type: str
    filename: str
    status: str
    created_at: datetime
    created_by: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    error: str | None = None


class ImportPreviewResponse(BaseModel):
    """Respuesta del preview — incluye samples por bucket y rows plano."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    type: str
    filename: str
    status: str
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    samples: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class ImportRunStatusResponse(BaseModel):
    """Estado actual + (si aplicado) detalles del apply."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    type: str
    filename: str
    status: str
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    apply: dict[str, Any] | None = None
    reconciliation: ReconciliationResultSchema | None = None
    error: str | None = None


class ReconciliationResultSchema(BaseModel):
    """Resultado de reconciliación tras un apply PIM."""

    model_config = ConfigDict(extra="ignore")

    total_excel_rows: int
    inserted: int
    updated: int
    no_change: int
    error_rows: int
    locked_rows: int
    accounted_total: int
    gap: int
    is_complete: bool
    missing_skus: list[str]


class ColumnMappingItemSchema(BaseModel):
    """Un ítem del mapeo columna Excel → campo product."""

    model_config = ConfigDict(extra="ignore")

    excel_col: str
    target_field: str
    transform: str = "text"
    confidence: float = 1.0
    notes: str = ""


class AnalyzeImportResponse(BaseModel):
    """Respuesta del endpoint POST /imports/analyze."""

    model_config = ConfigDict(extra="ignore")

    filename: str
    detected_header_row: int
    headers: list[str]
    sample_rows: list[list[str | None]]
    proposed_mapping: list[ColumnMappingItemSchema]
