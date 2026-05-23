"""Schemas Pydantic del módulo Scraper Source Builder.

Bloque 1: estructura de la receta (validación del JSONB).
Bloque 2 (Task 10): schemas request/response de la API.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class RecipeTransform(BaseModel):
    """Transform declarativo de un field. Snippets LLM no entran en F1."""

    op: Literal["regex_capture", "strip_currency", "replace", "map_values", "unit_factor"]
    pattern: str | None = None
    find: str | None = None
    replace_with: str | None = None
    mapping: dict[str, str] | None = None
    factor: float | None = None


class RecipeField(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    selector: str = Field(min_length=1)
    extract: str = Field(default="text")
    type: Literal["str", "float", "int", "currency", "bool"] = "str"
    transform: RecipeTransform | None = None

    @field_validator("extract")
    @classmethod
    def _valid_extract(cls, v: str) -> str:
        if v in ("text", "html") or v.startswith("attr:"):
            return v
        raise ValueError("extract debe ser 'text', 'html', o 'attr:<nombre>'")


class RecipeUrlTemplates(BaseModel):
    search: str | None = None
    pdp: str | None = None
    list: str | None = None
    product: str | None = None


class RecipePagination(BaseModel):
    next_selector: str | None = None
    max_pages: int = Field(default=1, ge=1, le=50)


class Recipe(BaseModel):
    url_templates: RecipeUrlTemplates
    list_item_selector: str | None = None
    pagination: RecipePagination | None = None
    fields: list[RecipeField] = Field(min_length=1)
    anti_bot_hints: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Task 10 — API request / response schemas
# ---------------------------------------------------------------------------
from datetime import datetime
from uuid import UUID


class ScraperSourceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    slug: str = Field(min_length=1, max_length=80, pattern=r"^[a-z0-9-]+$")
    base_url: str = Field(min_length=1)
    destination_profile: Literal["competitor_price", "product_data"]
    fetch_mode: Literal["static", "headless", "stealth"] = "static"
    description: str | None = None
    competitor_brand_id: UUID | None = None


class ScraperSourceRead(BaseModel):
    id: UUID
    name: str
    slug: str
    base_url: str
    description: str | None
    destination_profile: str
    fetch_mode: str
    status: str
    competitor_brand_id: UUID | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RecipeSubmit(BaseModel):
    """Receta enviada por el cliente — se valida contra el schema Recipe."""

    recipe: Recipe


class RecipeRead(BaseModel):
    id: UUID
    source_id: UUID
    version: int
    is_live: bool
    validation_status: str
    has_unapproved_snippet: bool
    recipe: dict[str, Any]

    model_config = {"from_attributes": True}


class ValidateRequest(BaseModel):
    recipe_id: UUID
    test_url: str = Field(min_length=1)


class ValidateResponse(BaseModel):
    status: str
    field_results: dict[str, str]
    records: list[dict[str, Any]]


class ActivateRequest(BaseModel):
    """Body de activación — solo necesita la receta a promover a is_live."""

    recipe_id: UUID
