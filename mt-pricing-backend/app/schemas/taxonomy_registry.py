"""Pydantic schemas — Registry polimórfico de taxonomías.

Schemas para CRUD del registry. Validaciones espejo de los CHECK constraints
declarados en migración 049 + modelo ORM ``app.db.models.taxonomy_registry``.

Endpoints (futuro PR):
- ``GET /taxonomies/registry`` → lista de ``TaxonomyTypeRead`` (drives sidebar)
- ``POST /taxonomies/types`` → crea ``TaxonomyType`` (admin only)
- ``GET /taxonomies/{slug}/nodes`` → lista nodos
- ``POST /taxonomies/{slug}/nodes`` → crea nodo
- ``POST /products/{sku}/taxonomies/{node_id}`` → link con role
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.db.models.taxonomy_registry import LINK_ROLES, VALUE_KINDS

# Slugs: lowercase, comienza con letra, permite a-z 0-9 _
SLUG_PATTERN = re.compile(r"^[a-z][a-z0-9_]*$")


def _validate_slug(value: str) -> str:
    if not SLUG_PATTERN.match(value):
        msg = (
            f"slug inválido: '{value}'. Debe coincidir con {SLUG_PATTERN.pattern} "
            f"(minúsculas, comienza con letra, permite dígitos y guión bajo)."
        )
        raise ValueError(msg)
    return value


# Literal types derivados de las constantes del modelo — fuente única de verdad.
ValueKindLiteral = Literal[
    "enum_closed",
    "enum_open",
    "numeric_with_unit",
    "freetext",
    "reference_to_other_type",
]
LinkRoleLiteral = Literal["belongs_to", "compatible_with", "replaces", "recommends"]

# Sanity: los Literal types deben coincidir con las constantes del modelo.
assert set(VALUE_KINDS) == {
    "enum_closed",
    "enum_open",
    "numeric_with_unit",
    "freetext",
    "reference_to_other_type",
}, "VALUE_KINDS desincronizado con ValueKindLiteral"
assert set(LINK_ROLES) == {
    "belongs_to",
    "compatible_with",
    "replaces",
    "recommends",
}, "LINK_ROLES desincronizado con LinkRoleLiteral"


# ---------------------------------------------------------------------------
# TaxonomyType
# ---------------------------------------------------------------------------


class TaxonomyTypeBase(BaseModel):
    """Campos compartidos entre create/read."""

    model_config = ConfigDict(extra="forbid")

    label_i18n: dict[str, str] = Field(
        default_factory=dict,
        description="Labels por locale: {es: ..., en: ..., ar: ...}",
    )
    is_hierarchical: bool = Field(default=False)
    depth_max: int | None = Field(default=None, gt=0)
    value_kind: ValueKindLiteral = Field(default="enum_open")
    filterable: bool = Field(default=True)
    display_order: int = Field(default=0)
    ui_layout: dict[str, Any] = Field(default_factory=dict)
    governance_policy: dict[str, Any] = Field(default_factory=dict)
    required_for_products: bool = Field(default=False)
    external_mappings: dict[str, Any] = Field(default_factory=dict)
    active: bool = Field(default=True)


class TaxonomyTypeCreate(TaxonomyTypeBase):
    """Body para POST /taxonomies/types."""

    slug: str = Field(min_length=1, max_length=64)

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        return _validate_slug(v)


class TaxonomyTypeUpdate(BaseModel):
    """Body para PATCH /taxonomies/types/{slug}. Todos los campos opcionales.

    ``slug`` NO es editable; usar ``TaxonomyAlias`` para evolución.
    """

    model_config = ConfigDict(extra="forbid")

    label_i18n: dict[str, str] | None = None
    is_hierarchical: bool | None = None
    depth_max: int | None = Field(default=None, gt=0)
    value_kind: ValueKindLiteral | None = None
    filterable: bool | None = None
    display_order: int | None = None
    ui_layout: dict[str, Any] | None = None
    governance_policy: dict[str, Any] | None = None
    required_for_products: bool | None = None
    external_mappings: dict[str, Any] | None = None
    active: bool | None = None


class TaxonomyTypeRead(TaxonomyTypeBase):
    """Respuesta para GET /taxonomies/types/{slug} y /registry."""

    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    slug: str
    is_system: bool
    schema_version: int
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# TaxonomyNode
# ---------------------------------------------------------------------------


class TaxonomyNodeBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: dict[str, str] = Field(default_factory=dict)
    attributes: dict[str, Any] = Field(default_factory=dict)
    display_order: int = Field(default=0)
    valid_from: datetime | None = None
    valid_until: datetime | None = None
    node_acl: dict[str, Any] | None = None
    active: bool = Field(default=True)


class TaxonomyNodeCreate(TaxonomyNodeBase):
    slug: str = Field(min_length=1, max_length=128)
    parent_id: UUID | None = None
    additional_parents: list[UUID] = Field(
        default_factory=list,
        description=(
            "IDs adicionales de parents para multi-inheritance. "
            "El primer parent es siempre ``parent_id`` (primary)."
        ),
    )

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        return _validate_slug(v)


class TaxonomyNodeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    labels: dict[str, str] | None = None
    attributes: dict[str, Any] | None = None
    display_order: int | None = None
    valid_until: datetime | None = None
    superseded_by: UUID | None = None
    node_acl: dict[str, Any] | None = None
    active: bool | None = None


class TaxonomyNodeRead(TaxonomyNodeBase):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    type_id: UUID
    type_slug: str | None = None
    slug: str
    parent_id: UUID | None
    superseded_by: UUID | None
    valid_from: datetime
    created_at: datetime
    updated_at: datetime


# ---------------------------------------------------------------------------
# TaxonomyAlias
# ---------------------------------------------------------------------------


class TaxonomyAliasCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias_slug: str = Field(min_length=1, max_length=128)
    canonical_node_id: UUID
    valid_until: datetime | None = None

    @field_validator("alias_slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        return _validate_slug(v)


class TaxonomyAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    alias_slug: str
    type_id: UUID
    canonical_node_id: UUID
    valid_until: datetime | None
    created_at: datetime


# ---------------------------------------------------------------------------
# ProductTaxonomyLink
# ---------------------------------------------------------------------------


class ProductTaxonomyLinkCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    node_id: UUID
    role: LinkRoleLiteral = Field(default="belongs_to")
    weight: int = Field(default=0)
    valid_from: datetime | None = None
    valid_until: datetime | None = None


class ProductTaxonomyLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    product_sku: str
    node_id: UUID
    role: LinkRoleLiteral
    weight: int
    valid_from: datetime
    valid_until: datetime | None
    created_by: UUID | None
    created_at: datetime


# ---------------------------------------------------------------------------
# FamilySchema
# ---------------------------------------------------------------------------


class FamilySchemaCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    family_slug: str = Field(min_length=1, max_length=64)
    schema_version: int = Field(default=1, ge=1)
    json_schema: dict[str, Any]
    description: str | None = None

    @field_validator("family_slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        return _validate_slug(v)


class FamilySchemaRead(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="forbid")

    id: UUID
    family_slug: str
    schema_version: int
    json_schema: dict[str, Any]
    description: str | None
    is_active: bool
    valid_from: datetime
    superseded_by: UUID | None
    created_at: datetime
    updated_at: datetime
