from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class TaxonomyProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    family: str
    weights: dict[str, float]
    hard_blockers: list[str]
    description: str | None = None


class TaxonomyProfileUpdate(BaseModel):
    weights: dict[str, float] = Field(..., description="Pesos por dimensión")
    hard_blockers: list[str] = Field(default_factory=list)
    description: str | None = None

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> TaxonomyProfileUpdate:
        total = sum(self.weights.values())
        if abs(total - 1.0) > 0.001:
            raise ValueError(f"Los pesos deben sumar 1.0 (actual: {total:.4f})")
        return self


class UnitTransformResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    transform_type: str
    from_unit: str
    to_unit: str
    formula: str | None = None
    lookup_table: dict | None = None
    description: str | None = None


class UnitTransformCreate(BaseModel):
    transform_type: str = Field(..., pattern="^(numeric|lookup|nominal)$")
    from_unit: str
    to_unit: str
    formula: str | None = None
    lookup_table: dict | None = None
    description: str | None = None


class NormEquivalenceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    norm_a: str
    system_a: str
    norm_b: str
    system_b: str
    equivalence_type: str
    notes: str | None = None


class NormEquivalenceCreate(BaseModel):
    norm_a: str
    system_a: str
    norm_b: str
    system_b: str
    equivalence_type: str = Field(..., pattern="^(exact|subset|compatible)$")
    notes: str | None = None


class ComparatorConfigEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    key: str
    value: Any
    description: str | None = None


class ComparatorConfigUpdate(BaseModel):
    value: Any


class ProfileMetrics(BaseModel):
    total_matches: int
    confirmed: int
    rejected: int
    confirmation_rate: float | None
    fp_rate: float | None
    days: int


class RuleSuggestionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    taxonomy_profile_id: UUID | None
    suggestion_type: str
    analysis_summary: str | None
    proposed_change: dict
    status: str
