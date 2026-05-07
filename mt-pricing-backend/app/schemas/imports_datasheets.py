"""Pydantic schemas para `/imports/datasheets/*` (US-1A-06-04)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ImportDatasheetsApplyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    confirm: bool = Field(default=True)


class DatasheetsDiffSample(BaseModel):
    model_config = ConfigDict(extra="ignore")
    row_index: int
    filename: str
    kind: str
    product_sku: str
    storage_path: str
    specs: dict[str, Any] = Field(default_factory=dict)
    file_size_bytes: int


class ImportDatasheetsPreviewResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str
    kind: str
    status: str
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    orphan_files: list[dict[str, Any]] = Field(default_factory=list)
    orphan_skus: list[str] = Field(default_factory=list)
    samples: list[DatasheetsDiffSample] = Field(default_factory=list)


class ImportDatasheetsRunStatusResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    run_id: str
    kind: str
    status: str
    created_at: datetime
    summary: dict[str, Any] = Field(default_factory=dict)
    orphan_files: list[dict[str, Any]] = Field(default_factory=list)
    orphan_skus: list[str] = Field(default_factory=list)
    apply: dict[str, Any] | None = None
    error: str | None = None


__all__ = [
    "DatasheetsDiffSample",
    "ImportDatasheetsApplyRequest",
    "ImportDatasheetsPreviewResponse",
    "ImportDatasheetsRunStatusResponse",
]
