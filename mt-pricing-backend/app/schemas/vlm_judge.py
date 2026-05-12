"""Schema Pydantic para respuesta del VLM Judge (US-F15-02-02).

Valida el JSON que devuelve claude-sonnet-4-6. Si la respuesta no es JSON
válido, el adapter devuelve fallback uncertain/0.0 (AC#2).
"""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator


class ClaudeJudgeResponse(BaseModel):
    """JSON exacto esperado de claude-sonnet-4-6 en modo VLM judge."""

    verdict: Literal["match", "reject", "uncertain"]
    confidence: Annotated[float, Field(ge=0.0, le=1.0)]
    reasoning: str
    deal_breakers_triggered: list[str] = []
    image_regions: list[dict[str, str]] = []

    @field_validator("confidence", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


__all__ = ["ClaudeJudgeResponse"]
