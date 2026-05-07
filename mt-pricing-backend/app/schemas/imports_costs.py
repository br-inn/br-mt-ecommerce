"""Pydantic schemas para `/imports/costs/*` (US-1A-06-02)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImportCostsApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool = Field(default=True, description="Idem PIM — placeholder.")


class ImportCostsRunSummary(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str
    kind: str
    filename: str
    status: str
    created_at: datetime
    created_by: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
    orphans: dict[str, list[str]] = Field(default_factory=dict)
    error: str | None = None


class ImportCostsPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str
    kind: str
    filename: str
    status: str
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    orphans: dict[str, list[str]] = Field(default_factory=dict)
    samples: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class ImportCostsRunStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str
    kind: str
    filename: str
    status: str
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    orphans: dict[str, list[str]] = Field(default_factory=dict)
    apply: dict[str, Any] | None = None
    error: str | None = None
