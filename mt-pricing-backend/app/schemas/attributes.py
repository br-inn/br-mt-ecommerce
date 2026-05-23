"""Pydantic V2 schemas — Fase 2 EAV typed attributes.

Convenciones:
- ConfigDict(from_attributes=True) en Response models (ORM).
- ConfigDict(extra='forbid', str_strip_whitespace=True) en Create/Patch.
- Validators garantizan integridad EAV: el ``data_type`` declarado en
  AttributeDefinition determina qué campo de AttributeValue debe estar
  poblado.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ---------------------------------------------------------------------------
# Tipos básicos
# ---------------------------------------------------------------------------
_CODE_PATTERN = r"^[a-zA-Z][a-zA-Z0-9_]{0,63}$"
"""Permite mayúsculas para preservar códigos ISO como F03, F10."""

DataType = Literal["number", "integer", "text", "bool", "enum", "range", "dimension"]
Scope = Literal["product", "variant", "both"]
OwnerType = Literal["product", "variant"]


# ===========================================================================
# AttributeDefinition
# ===========================================================================
class AttributeDefinitionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(
        min_length=1,
        max_length=64,
        pattern=_CODE_PATTERN,
        description="Unique identifier in snake_case English.",
    )
    label_en: str = Field(min_length=1, max_length=256)
    data_type: DataType
    unit: str | None = Field(default=None, max_length=32)
    description_en: str | None = Field(default=None, max_length=2048)
    is_filterable: bool = False
    is_seo_relevant: bool = False
    scope: Scope = "product"


class AttributeDefinitionCreate(AttributeDefinitionBase):
    pass


class AttributeDefinitionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label_en: str | None = Field(default=None, min_length=1, max_length=256)
    data_type: DataType | None = None
    unit: str | None = Field(default=None, max_length=32)
    description_en: str | None = Field(default=None, max_length=2048)
    is_filterable: bool | None = None
    is_seo_relevant: bool | None = None
    scope: Scope | None = None


class AttributeDefinitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    code: str
    label_en: str
    data_type: DataType
    unit: str | None
    description_en: str | None
    is_filterable: bool
    is_seo_relevant: bool
    scope: Scope
    created_at: datetime


# ===========================================================================
# AttributeOption
# ===========================================================================
class AttributeOptionBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    code: str = Field(min_length=1, max_length=64, pattern=_CODE_PATTERN)
    label_en: str = Field(min_length=1, max_length=256)
    order_index: int = Field(default=0, ge=0, le=32767)


class AttributeOptionCreate(AttributeOptionBase):
    pass


class AttributeOptionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    label_en: str | None = Field(default=None, min_length=1, max_length=256)
    order_index: int | None = Field(default=None, ge=0, le=32767)


class AttributeOptionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    attribute_id: UUID
    code: str
    label_en: str
    order_index: int


# ===========================================================================
# FamilyAttribute (template link)
# ===========================================================================
class FamilyAttributeBase(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    attribute_id: UUID
    group_code: str = Field(min_length=1, max_length=64)
    order_index: int = Field(default=0, ge=0, le=32767)
    is_required: bool = False
    default_value: str | None = Field(default=None, max_length=1024)
    validation_rule: dict[str, Any] | None = None


class FamilyAttributeCreate(FamilyAttributeBase):
    pass


class FamilyAttributePatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    group_code: str | None = Field(default=None, min_length=1, max_length=64)
    order_index: int | None = Field(default=None, ge=0, le=32767)
    is_required: bool | None = None
    default_value: str | None = None
    validation_rule: dict[str, Any] | None = None


class FamilyAttributeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    family_id: UUID
    attribute_id: UUID
    group_code: str
    order_index: int
    is_required: bool
    default_value: str | None
    validation_rule: dict[str, Any] | None


class FamilyAttributeWithDefinition(FamilyAttributeResponse):
    """Family template enriched with the underlying AttributeDefinition."""

    attribute: AttributeDefinitionResponse


# ===========================================================================
# AttributeValue (upsert payloads + responses)
# ===========================================================================
class AttributeValueBase(BaseModel):
    """Generic payload for upserting a value of any data_type.

    Only one of value_* fields should be populated, matching the
    AttributeDefinition.data_type. Validators enforce this on best-effort:
    server-side service validates the strict mapping once it knows the
    attribute's data_type.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    value_number: Decimal | None = None
    value_text: str | None = Field(default=None, max_length=4000)
    value_bool: bool | None = None
    value_enum_id: UUID | None = None
    value_min: Decimal | None = None
    value_max: Decimal | None = None
    unit: str | None = Field(default=None, max_length=32)
    language: str | None = Field(default=None, min_length=2, max_length=2)

    @model_validator(mode="after")
    def _require_at_least_one(self) -> AttributeValueBase:
        populated = [
            self.value_number is not None,
            self.value_text is not None and self.value_text != "",
            self.value_bool is not None,
            self.value_enum_id is not None,
            (self.value_min is not None) or (self.value_max is not None),
        ]
        if not any(populated):
            raise ValueError(
                "At least one of value_number, value_text, value_bool, "
                "value_enum_id, or (value_min/value_max) must be set."
            )
        return self

    @model_validator(mode="after")
    def _range_consistency(self) -> AttributeValueBase:
        if (
            self.value_min is not None
            and self.value_max is not None
            and self.value_min > self.value_max
        ):
            raise ValueError("value_min must be <= value_max.")
        return self


class AttributeValueCreate(AttributeValueBase):
    """Upsert payload — used by PUT /products/{sku}/attributes/{attr_code}."""

    pass


class AttributeValuePatch(AttributeValueBase):
    """Patch payload — same shape, validators identical to Create."""

    pass


class AttributeValueResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_type: OwnerType
    owner_id: str
    attribute_id: UUID
    value_number: Decimal | None
    value_text: str | None
    value_bool: bool | None
    value_enum_id: UUID | None
    value_min: Decimal | None
    value_max: Decimal | None
    unit: str | None
    language: str | None


class AttributeValueWithDefinition(AttributeValueResponse):
    """Value response enriched with the underlying AttributeDefinition.

    Used by GET /products/{sku}/attributes for UI rendering.
    """

    attribute_code: str
    attribute_label_en: str
    data_type: DataType


# ---------------------------------------------------------------------------
# Helper validators (used by service layer or tests)
# ---------------------------------------------------------------------------
def _expected_field_for_data_type(data_type: DataType) -> tuple[str, ...]:
    """Return the AttributeValue field name(s) that must be set for a given type."""
    mapping: dict[str, tuple[str, ...]] = {
        "number": ("value_number",),
        "integer": ("value_number",),
        "text": ("value_text",),
        "bool": ("value_bool",),
        "enum": ("value_enum_id",),
        "range": ("value_min", "value_max"),
        "dimension": ("value_number",),
    }
    return mapping[data_type]


def validate_value_matches_type(payload: AttributeValueBase, data_type: DataType) -> None:
    """Raise ValueError if the populated payload field does not match data_type.

    Used by the service layer once it has loaded the AttributeDefinition.
    Not exposed via Pydantic-only because the data_type comes from DB.
    """
    expected = _expected_field_for_data_type(data_type)
    # For text/bool/number/enum/dimension expect exactly one of the expected
    # to be non-None; for range expect at least one of value_min/value_max.
    if data_type == "range":
        if payload.value_min is None and payload.value_max is None:
            raise ValueError("data_type=range requires value_min and/or value_max.")
        return

    field = expected[0]
    populated_field_value = getattr(payload, field)
    if populated_field_value is None:
        raise ValueError(f"data_type={data_type} requires field '{field}' to be set.")
    # Verify no other typed fields are also set (range excepted above).
    other_fields = (
        "value_number",
        "value_text",
        "value_bool",
        "value_enum_id",
    )
    range_set = (payload.value_min is not None) or (payload.value_max is not None)
    extras = [f for f in other_fields if f != field and getattr(payload, f) is not None]
    if extras or range_set:
        raise ValueError(
            f"data_type={data_type} expects only '{field}'; got "
            f"additional populated fields: {extras + (['value_min/value_max'] if range_set else [])}"
        )
