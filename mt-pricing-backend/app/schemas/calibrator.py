"""Pydantic schemas — calibrator admin API (US-1A-09-07)."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class CalibratorActiveResponse(BaseModel):
    """Respuesta de ``GET /admin/calibrator/active``."""

    model_config = ConfigDict(extra="forbid")

    version: str | None = None
    trained_on_count: int = 0
    brier_score: float | None = None
    ece: float | None = None
    is_active: bool = False
    trained_at: datetime | None = None
    promoted_at: datetime | None = None


class CalibratorTrainRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    auto_promote: bool = Field(
        default=False,
        description="Si True, promueve la versión entrenada cuando mejora ECE ≥ 5%.",
    )
    since_days: int | None = Field(
        default=None,
        ge=1,
        description="Cutoff de golden_labels.judged_at (días atrás). Default 90.",
    )
    version: str | None = Field(
        default=None,
        description="Stamp opaco override. Default ``s5-YYYYMMDDHHMMSS``.",
    )


class CalibratorTrainResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    trained_on_count: int
    brier_before: float
    brier_after: float
    ece_before: float
    ece_after: float
    auto_promoted: bool


class CalibratorPromoteResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str
    is_active: bool
    promoted_at: datetime | None = None


__all__ = [
    "CalibratorActiveResponse",
    "CalibratorPromoteResponse",
    "CalibratorTrainRequest",
    "CalibratorTrainResponse",
]
