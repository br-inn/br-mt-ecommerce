"""Pydantic schemas para los endpoints añadidos en Sprint 4 (US-1B-01-04).

- ``BulkPublishRequest`` / ``BulkPublishResponse``.
- ``RecalcBatchRequest`` / ``RecalcBatchResponse``.
- ``CounterProposalRequest`` / ``CounterProposalResponse``.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Bulk publish
# ---------------------------------------------------------------------------
class BulkPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price_ids: list[UUID] = Field(min_length=1, max_length=1000)
    rollback_on_error: bool = Field(default=False)
    reason: str | None = Field(default=None, max_length=2048)


class BulkPublishResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    total: int
    published_count: int
    published: list[str] = Field(default_factory=list)
    queue_failed: list[dict[str, Any]] = Field(default_factory=list)
    errors: list[dict[str, Any]] = Field(default_factory=list)
    rolled_back: bool = False


# ---------------------------------------------------------------------------
# Recalc batch
# ---------------------------------------------------------------------------
class RecalcBatchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    skus: list[str] = Field(min_length=1, max_length=500)
    trigger: str = Field(default="manual", max_length=32)


class RecalcBatchResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    skus_queued: int
    task_ids: list[str] = Field(default_factory=list)
    trigger: str


# ---------------------------------------------------------------------------
# Counter-proposal (revise)
# ---------------------------------------------------------------------------
class CounterProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2048)


class CounterProposalResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    price_id: str
    new_amount: str
    old_amount: str
    margin_pct: str | None = None
    reason: str
    status_after: str


__all__ = [
    "BulkPublishRequest",
    "BulkPublishResponse",
    "CounterProposalRequest",
    "CounterProposalResponse",
    "RecalcBatchRequest",
    "RecalcBatchResponse",
]
