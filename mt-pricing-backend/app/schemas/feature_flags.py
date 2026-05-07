"""Pydantic schemas — feature flags admin API (US-1A-09-08).

Diseño minimal: en S5 sólo soportamos flags booleanos. Pydantic v2 con
``ConfigDict(extra='forbid')`` para fail-fast en payloads malformados.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class FeatureFlagItem(BaseModel):
    """Snapshot de un flag para list/detail."""

    model_config = ConfigDict(extra="forbid")

    key: str
    enabled: bool
    updated_by: UUID | None = None
    updated_at: datetime | None = None
    created_at: datetime | None = None


class FeatureFlagListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    flags: list[FeatureFlagItem] = Field(default_factory=list)


class FeatureFlagUpdateRequest(BaseModel):
    """Body de ``PATCH /admin/flags/{key}``."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool


class KillSwitchRequest(BaseModel):
    """Body de ``POST /admin/flags/kill-switch``."""

    model_config = ConfigDict(extra="forbid")

    engaged: bool = Field(..., description="True = engage, False = disengage.")
    reason: str | None = Field(
        default=None,
        max_length=280,
        description="Motivo del toggle (audit trail).",
    )


class KillSwitchResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    engaged: bool
    updated_by: UUID | None = None
    updated_at: datetime | None = None


__all__ = [
    "FeatureFlagItem",
    "FeatureFlagListResponse",
    "FeatureFlagUpdateRequest",
    "KillSwitchRequest",
    "KillSwitchResponse",
]
