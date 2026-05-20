# app/schemas/match_agent.py
"""Pydantic schemas — MatchValidationAgent (config, métricas, decisiones)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

AgentMode = Literal["shadow", "active"]
AgentVerdict = Literal["auto_validate", "auto_discard", "human"]
AgentSignal = Literal["conformal", "bootstrap"]


class MatchAgentConfigResponse(BaseModel):
    """Fila singleton de configuración del agente."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    mode: AgentMode
    alpha: Decimal
    min_labels_gate: int
    updated_at: datetime


class MatchAgentConfigUpdate(BaseModel):
    """Body de PUT /matches/agent/config — todos los campos opcionales."""

    model_config = ConfigDict(extra="forbid")

    mode: AgentMode | None = None
    alpha: Decimal | None = Field(default=None, gt=0, lt=1)
    min_labels_gate: int | None = Field(default=None, ge=1)


class MatchAgentMetrics(BaseModel):
    """Métricas del agente para el panel de la UI."""

    model_config = ConfigDict(extra="forbid")

    golden_labels_total: int
    min_labels_gate: int
    gate_reached: bool
    shadow_decisions: int
    shadow_precision: float | None = Field(
        default=None,
        description="Aciertos / decisiones con human_outcome conocido. None si no hay datos.",
    )
    calibrator_version: str | None = None
    calibrator_brier: float | None = None
    calibrator_ece: float | None = None
    calibrator_trained_on: int | None = None
    mode: AgentMode


class MatchAgentDecisionResponse(BaseModel):
    """Una decisión registrada del agente."""

    model_config = ConfigDict(extra="forbid", from_attributes=True)

    id: UUID
    candidate_id: UUID
    product_sku: str
    verdict: AgentVerdict
    mode: AgentMode
    applied: bool
    signal: AgentSignal
    score: int
    calibrated_confidence: Decimal | None = None
    review_priority: str | None = None
    calibrator_version: str | None = None
    human_outcome: str | None = None
    created_at: datetime
