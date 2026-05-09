"""Wave 10 — Facets response schema for GET /api/v1/products/facets."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class FacetBucket(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    count: int = Field(ge=0)


class TranslationLangFacet(BaseModel):
    model_config = ConfigDict(extra="forbid")
    approved: int = Field(ge=0, default=0)
    pending: int = Field(ge=0, default=0)
    draft: int = Field(ge=0, default=0)
    missing: int = Field(ge=0, default=0)


class FacetsResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    total: int = Field(ge=0)
    total_unfiltered: int = Field(ge=0)
    family: list[FacetBucket] = Field(default_factory=list)
    material: list[FacetBucket] = Field(default_factory=list)
    dn: list[FacetBucket] = Field(default_factory=list)
    pn: list[FacetBucket] = Field(default_factory=list)
    data_quality: dict[str, int] = Field(default_factory=dict)
    active: dict[str, int] = Field(default_factory=dict)
    image_status: dict[str, int] = Field(default_factory=dict)
    has_image: dict[str, int] = Field(default_factory=dict)
    translation_status: dict[str, TranslationLangFacet] = Field(default_factory=dict)
    # ---- Stage 3 (Wave 11) — division/series/tier/material vocab ---------
    division: list[FacetBucket] = Field(default_factory=list)
    series: list[FacetBucket] = Field(default_factory=list)
    tier_code: list[FacetBucket] = Field(default_factory=list)
    material_curated: list[FacetBucket] = Field(default_factory=list)
