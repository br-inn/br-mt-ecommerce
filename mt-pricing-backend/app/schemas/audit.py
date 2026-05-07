"""Schemas para `/api/v1/audit/*` — exposición de la timeline de eventos.

Sprint 1.5 (US-1A-07-01): el endpoint sirve como source-of-truth para todos
los timelines de la UI (producto, usuario, job, role). Devuelve paginación
keyset opaca codificada como base64url-JSON, igual que el resto de listados.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class AuditActorRef(BaseModel):
    """Referencia al actor de un audit event (puede ser nulo para system events)."""

    model_config = ConfigDict(extra="forbid")

    id: UUID | None = None
    email: str | None = None
    full_name: str | None = None


class AuditEventResponse(BaseModel):
    """Audit event tal como se expone al frontend.

    El `id` se serializa como string para evitar pérdida de precisión en JS
    (BigInt en backend, Number sólo soporta 2^53). El cliente lo trata como
    opaque ID.
    """

    model_config = ConfigDict(extra="forbid")

    id: str = Field(description="Audit event id (BigInt serializado como string).")
    event_at: datetime
    actor: AuditActorRef | None = None
    entity_type: str
    entity_id: str
    action: str
    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None
    payload_diff: dict[str, Any] = Field(default_factory=dict)
    reason: str | None = None
    request_id: str | None = None
    current_hash: str | None = None
    prev_hash: str | None = None
