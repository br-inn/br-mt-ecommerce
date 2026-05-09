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
    """Respuesta del preview — incluye samples por bucket."""

    model_config = ConfigDict(extra="ignore")

    run_id: str
    type: str
    filename: str
    status: str
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    samples: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


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
    error: str | None = None
