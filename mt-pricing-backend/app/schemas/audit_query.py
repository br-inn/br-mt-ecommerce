"""Schemas para `/api/v1/audit-events` — query multi-entidad (US-1A-07-03 backend).

Distintos del legacy `app/schemas/audit.py` (US-1A-07-01 — un solo entity_type)
porque el tab Auditoría de la UI necesita un timeline unificado por SKU que
mezcla `products`, `costs`, `prices`, `product_translations`. Se mantienen
ambos schemas para no romper el contrato consumido por los timelines de
usuario / job.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditQueryActor(BaseModel):
    """Actor enriquecido — id + email + full_name si user existe."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    email: str | None = None
    full_name: str | None = None


class AuditQueryItem(BaseModel):
    """Una entrada del timeline multi-entidad."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Audit event id (BigInt → string).")
    event_at: datetime
    entity_type: str
    entity_id: str
    action: str
    actor: AuditQueryActor | None = None
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    payload_diff: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None


class AuditQueryCursor(BaseModel):
    """Cursor opaco — base64url(json({"at":<iso>,"id":<bigint>}))."""

    model_config = ConfigDict(extra="forbid")
    next: str | None = None


class AuditQueryResponse(BaseModel):
    """Respuesta paginada de `/api/v1/audit-events`."""

    model_config = ConfigDict(extra="forbid")

    items: list[AuditQueryItem]
    cursor: AuditQueryCursor = Field(default_factory=AuditQueryCursor)
    page_size: int = Field(ge=1, le=200)
