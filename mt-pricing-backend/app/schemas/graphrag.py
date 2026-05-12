"""Pydantic schemas — GraphRAG API (US-RND-01-11)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class GraphRagHealthResponse(BaseModel):
    """Respuesta de ``GET /api/v1/graphrag/health``."""

    model_config = ConfigDict(extra="forbid")

    backend: str = Field(..., description="Identificador del adapter activo.")
    healthy: bool
    nodes: int = Field(ge=0)
    edges: int = Field(ge=0)
    cdc_events: dict[str, int] = Field(
        default_factory=dict,
        description="Conteo por status de la tabla cdc_events.",
    )


class GraphRagReplayRequest(BaseModel):
    """Body opcional de ``POST /api/v1/graphrag/replay`` (admin)."""

    model_config = ConfigDict(extra="forbid")

    entity_type: str | None = Field(
        default=None,
        description="Filtra por entity_type. None = todas las entidades.",
    )
    only_dead_letter: bool = Field(
        default=False,
        description="Si True, sólo resetea rows en `dead_letter`.",
    )


class GraphRagReplayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rows_reset: int = Field(ge=0)
    scope: Literal["all", "dead_letter_only"]
    entity_type: str | None = None


class KgMetricsResponse(BaseModel):
    """Respuesta de ``GET /api/v1/graphrag/metrics`` (US-F15-01-06)."""

    model_config = ConfigDict(extra="forbid")

    node_count: int = Field(ge=0)
    edge_count: int = Field(ge=0)
    orphan_nodes: int = Field(ge=0)
    cdc_lag_seconds: float = Field(ge=0.0)
    last_sync: str | None = None
    backend: str
    healthy: bool = True


__all__ = [
    "GraphRagHealthResponse",
    "GraphRagReplayRequest",
    "GraphRagReplayResponse",
    "KgMetricsResponse",
]
