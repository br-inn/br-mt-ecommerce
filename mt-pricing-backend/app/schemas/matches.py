"""Pydantic schemas — Match candidates API.

Alineado con `app/db/models/match_candidate.py` y el patrón de los demás
schemas (extra=forbid, from_attributes=True).
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ChannelStr = Literal["amazon_uae", "noon_uae"]
KindStr = Literal["peer", "drop", "unknown"]
StatusStr = Literal["pending", "validated", "discarded"]


SkuStr = Annotated[
    str,
    StringConstraints(
        min_length=1,
        max_length=64,
        strip_whitespace=True,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9\-_]{0,63}$",
    ),
]


class MatchCandidateBase(BaseModel):
    model_config = ConfigDict(extra="forbid", from_attributes=True)

    product_sku: str
    channel: ChannelStr
    external_id: str
    brand: str | None = None
    title: str
    price_aed: Decimal | None = None
    delivery_text: str | None = None
    specs_jsonb: dict[str, Any] = Field(default_factory=dict)
    kind: KindStr = "unknown"
    score: int = Field(ge=0, le=100)
    status: StatusStr = "pending"


class MatchCandidateResponse(MatchCandidateBase):
    """Item devuelto por GET /matches y endpoints de transición."""

    id: UUID
    validated_by: UUID | None = None
    validated_at: datetime | None = None
    discarded_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class MatchCandidateDetail(MatchCandidateResponse):
    """Detalle — incluye scoring breakdown extraído de specs_jsonb._scoring."""

    scoring: dict[str, Any] | None = Field(
        default=None,
        description="Breakdown de scoring extraído de specs_jsonb._scoring.",
    )


class MatchRefreshResponse(BaseModel):
    """Respuesta del POST /matches/{sku}/refresh."""

    model_config = ConfigDict(extra="forbid")

    sku: str
    refreshed_count: int = Field(ge=0)
    candidates: list[MatchCandidateResponse]


class MatchDiscardRequest(BaseModel):
    """Body opcional para POST /matches/{id}/discard."""

    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=512)
