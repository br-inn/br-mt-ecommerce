"""Pydantic v2 response schemas for F4 lineage/freshness/health/card endpoints."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class SourceHealthItem(BaseModel):
    source_op: str
    last_sync_attempt_at: datetime | None
    last_sync_success_at: datetime | None
    last_error: str | None
    freshness_sla_minutes: int
    age_minutes: int | None
    is_healthy: bool


class SourceHealthResponse(BaseModel):
    sources: list[SourceHealthItem] = []
    blocking: list[str] = []


class FreshnessItem(BaseModel):
    scope: str
    key: str
    source_op: str
    observed_at: datetime | None
    valid_until: datetime | None
    is_stale: bool


class FreshnessResponse(BaseModel):
    items: list[FreshnessItem] = []


class LineageComponent(BaseModel):
    key: str
    value: Decimal
    source_op: str | None
    source_ref: str | None
    observed_at: datetime | None
    is_stale: bool = False


class LineageLayer(BaseModel):
    layer: int
    label: str
    amount_aed: Decimal
    components: list[LineageComponent] = []


class LineageResponse(BaseModel):
    sku: str
    field: str
    total_aed: Decimal
    layers: list[LineageLayer] = []


class AuditEntry(BaseModel):
    actor_id: str | None
    action: str
    before: dict | None
    after: dict | None
    reason: str | None
    event_at: datetime


class ParameterAuditResponse(BaseModel):
    key: str
    entity_type: str
    entity_id: str
    entries: list[AuditEntry] = []


class ProductCardResponse(BaseModel):
    sku: str
    master: dict
    price_history: list[dict] = []
    listing: dict | None
    proposals: list[dict] = []


__all__ = [
    "AuditEntry",
    "FreshnessItem",
    "FreshnessResponse",
    "LineageComponent",
    "LineageLayer",
    "LineageResponse",
    "ParameterAuditResponse",
    "ProductCardResponse",
    "SourceHealthItem",
    "SourceHealthResponse",
]
