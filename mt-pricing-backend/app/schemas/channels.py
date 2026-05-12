"""Channel schemas — US-1B-03-02 (Sprint 8)."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ChannelTransitionRequest(BaseModel):
    target_state: str = Field(..., description="Estado destino de la transición")
    subset_skus: list[str] = Field(
        default_factory=list,
        description="SKUs del subset piloto (requerido para pre_launch → pilot)",
    )
    comment: str = Field(default="", description="Comentario de auditoría")
    override_warnings: bool = Field(
        default=False,
        description="Permite pilotar con SKUs sin precio aprobado",
    )


class ChannelTransitionResponse(BaseModel):
    channel_id: str
    channel_code: str
    from_state: str
    to_state: str
    pilot_with_warnings: bool
    missing_skus: list[str]
    history_id: str


class ChannelRead(BaseModel):
    id: UUID
    code: str
    name: str
    state: str
    pilot_with_warnings: bool
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChannelListResponse(BaseModel):
    items: list[ChannelRead]
    total: int


class ChannelHistoryEntry(BaseModel):
    id: UUID
    channel_id: UUID
    from_state: str | None
    to_state: str
    actor_user_id: UUID | None
    comment: str | None
    pilot_with_warnings: bool
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ChannelHistoryResponse(BaseModel):
    channel_id: UUID
    items: list[ChannelHistoryEntry]


__all__ = [
    "ChannelTransitionRequest",
    "ChannelTransitionResponse",
    "ChannelRead",
    "ChannelListResponse",
    "ChannelHistoryEntry",
    "ChannelHistoryResponse",
]
