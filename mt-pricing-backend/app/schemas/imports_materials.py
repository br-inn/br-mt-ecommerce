"""Pydantic schemas para `/imports/materials/*` (US-1A-06-03)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ImportMaterialsApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mode: Literal["replace", "append"] = "replace"


class ImportMaterialsPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str
    kind: str
    filename: str
    status: str
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    materials_columns: list[str] = Field(default_factory=list)
    samples: list[dict[str, Any]] = Field(default_factory=list)


class ImportMaterialsApplyResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str
    kind: str
    status: str
    summary: dict[str, Any] = Field(default_factory=dict)
    apply: dict[str, Any] | None = None
    error: str | None = None
