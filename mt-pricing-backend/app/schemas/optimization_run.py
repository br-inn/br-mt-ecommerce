"""Pydantic schemas para las alertas de drift de optimización (F8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import SellingModel


class OptimizationRunSummary(BaseModel):
    """Vista de lista — campos esenciales de una alerta de drift."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    selling_model: SellingModel
    skus_scheme_changed: int
    skus_signal_changed: int
    detected_at: datetime
    acknowledged_at: datetime | None


class OptimizationRunDetail(OptimizationRunSummary):
    """Vista de detalle — incluye el diff completo + razones + snapshots."""

    baseline_snapshot_id: UUID | None
    revert_snapshot_id: UUID | None
    drift_reasons: dict[str, Any]
    diff_detail: list[Any]


__all__ = ["OptimizationRunDetail", "OptimizationRunSummary"]
