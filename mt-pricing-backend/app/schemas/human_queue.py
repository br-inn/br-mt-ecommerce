"""Schemas — Human Queue API (US-RND-01-10).

Incluye:
- ``HumanQueueItem``   — item de la cola (extiende MatchCandidateResponse).
- ``HumanQueueList``   — respuesta paginada del GET /human-queue.
- ``LabelRequest``     — body del POST /human-queue/{id}/label.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

LabelLiteral = Literal["accept", "reject", "skip"]


class HumanQueueItem(BaseModel):
    """Item de la cola de validación humana."""

    model_config = ConfigDict(extra="ignore", from_attributes=True)

    id: UUID
    product_sku: str
    channel: str
    external_id: str
    brand: str | None = None
    title: str
    price_aed: Decimal | None = None
    specs_jsonb: dict = Field(default_factory=dict)
    kind: str = "unknown"
    score: int = Field(ge=0, le=100)
    status: str = "pending"
    calibrated_confidence: Decimal | None = None
    label: LabelLiteral | None = None
    reviewer_user_id: UUID | None = None
    reviewed_at: datetime | None = None
    validated_by: UUID | None = None
    validated_at: datetime | None = None
    discarded_reason: str | None = None
    created_at: datetime
    updated_at: datetime

    # VLM Judge (US-F15-02-02, AC#5/AC#6) — poblado desde specs_jsonb['vlm_judge'].
    # Nulo para rol viewer y cuando VLM no ha corrido.
    judge_rationale: str | None = None
    judge_image_regions: list[dict] | None = None


class HumanQueueList(BaseModel):
    """Respuesta paginada de GET /human-queue."""

    model_config = ConfigDict(extra="forbid")

    items: list[HumanQueueItem]
    total: int = Field(ge=0, description="Número de ítems en esta página")
    limit: int = Field(ge=1, le=200)
    offset: int = Field(ge=0)
    confidence_threshold: float = Field(ge=0.0, le=1.0)


class LabelRequest(BaseModel):
    """Body de POST /human-queue/{id}/label."""

    model_config = ConfigDict(extra="forbid")

    label: LabelLiteral = Field(description="Veredicto del revisor: accept / reject / skip")
