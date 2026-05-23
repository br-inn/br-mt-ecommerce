"""Schemas Pydantic para Channel Mirror endpoints.

Alineado con `mt-pricing-frontend/app/(app)/canales/amazon-uae/page.tsx`:
- ``MirrorRow`` (frontend) ↔ ``FieldDiffResponse`` (backend).
- ``SYNC_LOG`` (frontend) ↔ ``SyncLogEntry`` (backend).
- "Estado del listing" card ↔ ``ChannelListingResponse``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

CHANNEL_CODE_REGEX = r"^[a-z0-9_]{2,64}$"
ChannelCodeStr = Annotated[
    str,
    StringConstraints(min_length=2, max_length=64, pattern=CHANNEL_CODE_REGEX),
]


DiffStatusLiteral = Literal["match", "drift", "missing", "queued"]
BuyBoxStateLiteral = Literal["own", "competitor", "none"]


class FieldDiffResponse(BaseModel):
    """Una fila del comparador campo a campo."""

    model_config = ConfigDict(extra="forbid")

    field: str
    mt: Any
    live: Any
    status: DiffStatusLiteral
    lang: Literal["ar"] | None = None
    mono: bool = False
    notes: list[str] = Field(default_factory=list)


class DiffSummary(BaseModel):
    """Cuenta agregada por status (banner del frontend)."""

    model_config = ConfigDict(extra="forbid")

    match: int = 0
    drift: int = 0
    missing: int = 0
    queued: int = 0


class ChannelListingResponse(BaseModel):
    """Listing emparejado MT ↔ canal — fila del listado paginado."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    product_sku: str
    channel_code: str
    external_id: str
    buybox_state: BuyBoxStateLiteral
    buybox_pct_7d: Decimal | None = None
    stock_qty: int | None = None
    rating: Decimal | None = None
    reviews_count: int | None = None
    last_sync_at: datetime | None = None
    diff_summary: DiffSummary = Field(default_factory=DiffSummary)
    is_active: bool = True
    created_at: datetime
    updated_at: datetime


class DiffResponse(BaseModel):
    """Respuesta de ``GET /diff`` y ``POST /sync``."""

    model_config = ConfigDict(extra="forbid")

    channel_code: str
    sku: str
    external_id: str
    diffs: list[FieldDiffResponse]
    summary: DiffSummary
    fetched_at: datetime | None = None


class PublishRequest(BaseModel):
    """Body opcional para ``POST /publish``."""

    model_config = ConfigDict(extra="forbid")

    fields: list[str] | None = Field(
        default=None,
        description="Lista de fields a publicar. Si es None, todo el canonical.",
    )
    reason: str | None = Field(default=None, max_length=512)


class PublishResponseModel(BaseModel):
    """Resultado del intento de publicación."""

    model_config = ConfigDict(extra="forbid")

    ok: bool
    submission_id: str | None = None
    accepted_fields: list[str] = Field(default_factory=list)
    rejected_fields: list[str] = Field(default_factory=list)
    message: str | None = None


class SyncLogEntry(BaseModel):
    """Una entrada del Sync log card."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_code: str
    product_sku: str | None = None
    event_type: Literal["pull", "push", "diff"]
    ok: bool
    summary: str | None = None
    duration_ms: int | None = None
    created_at: datetime


__all__ = [
    "BuyBoxStateLiteral",
    "ChannelCodeStr",
    "ChannelListingResponse",
    "DiffResponse",
    "DiffStatusLiteral",
    "DiffSummary",
    "FieldDiffResponse",
    "PublishRequest",
    "PublishResponseModel",
    "SyncLogEntry",
]
