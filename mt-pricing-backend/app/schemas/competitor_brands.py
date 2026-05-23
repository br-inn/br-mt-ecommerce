"""Pydantic schemas para el módulo de marcas competidoras."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class CompetitorBrandCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    amazon_search_term: str | None = Field(None, max_length=200)
    amazon_dept: str = Field("industrial", max_length=100)
    amazon_category_node: str | None = Field(None, max_length=50)
    is_active: bool = True
    notes: str | None = None


class CompetitorBrandUpdate(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=200)
    amazon_search_term: str | None = None
    amazon_dept: str | None = Field(None, max_length=100)
    amazon_category_node: str | None = None
    is_active: bool | None = None
    notes: str | None = None


class CompetitorBrandRead(BaseModel):
    id: UUID
    name: str
    amazon_search_term: str | None
    amazon_dept: str
    amazon_category_node: str | None
    is_active: bool
    notes: str | None
    last_scraped_at: datetime | None
    # US-SCR-04-03: monitoreo continuo de precios activo para esta marca
    monitoring_active: bool = False
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class BrandScrapeRunRequest(BaseModel):
    brand_ids: list[UUID] | None = Field(
        None,
        description="UUIDs de las marcas a scrapear. None = todas las activas.",
    )
    force: bool = False


class BrandScrapeRunResponse(BaseModel):
    job_id: str | None
    total_brands: int
    status: str
