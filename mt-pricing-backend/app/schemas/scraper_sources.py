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
