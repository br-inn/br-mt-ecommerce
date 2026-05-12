"""Unit tests for Pydantic schemas — Fase 2 EAV typed attributes.

Covers:
- AttributeDefinitionCreate / Patch / Response: code pattern, scope enum,
  data_type enum.
- AttributeOptionCreate validations.
- AttributeValueBase: require-at-least-one validator + range consistency.
- validate_value_matches_type: per-data_type field mapping.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.attributes import (
    AttributeDefinitionCreate,
    AttributeOptionCreate,
    AttributeValueBase,
    AttributeValueCreate,
    FamilyAttributeCreate,
    validate_value_matches_type,
)

pytestmark = pytest.mark.unit


# ===========================================================================
# AttributeDefinitionCreate
# ===========================================================================
class TestAttributeDefinitionCreate:
    def test_valid_numeric(self) -> None:
        m = AttributeDefinitionCreate(
            code="dn_nominal",
            label_en="Nominal DN",
            data_type="integer",
            unit="mm",
            scope="variant",
            is_filterable=True,
        )
        assert m.code == "dn_nominal"
        assert m.data_type == "integer"
        assert m.scope == "variant"
        assert m.is_filterable is True
        # Defaults preserved
        assert m.is_seo_relevant is False

    def test_invalid_data_type(self) -> None:
        with pytest.raises(ValidationError):
            AttributeDefinitionCreate(
                code="foo",
                label_en="Foo",
                data_type="not_a_type",  # type: ignore[arg-type]
            )

    def test_invalid_scope(self) -> None:
        with pytest.raises(ValidationError):
            AttributeDefinitionCreate(
                code="foo",
                label_en="Foo",
                data_type="number",
                scope="unknown",  # type: ignore[arg-type]
            )

    def test_invalid_code_pattern_starts_with_digit(self) -> None:
        with pytest.raises(ValidationError):
            AttributeDefinitionCreate(
                code="2dn",
                label_en="X",
                data_type="number",
            )

    def test_valid_code_with_uppercase(self) -> None:
        # ISO codes like F03/F10 should be allowed once we permit uppercase.
        # Our pattern in schemas does allow uppercase.
        m = AttributeDefinitionCreate(
            code="ISO5211",
            label_en="ISO 5211",
            data_type="enum",
        )
        assert m.code == "ISO5211"

    def test_extra_field_forbidden(self) -> None:
        with pytest.raises(ValidationError):
            AttributeDefinitionCreate(
                code="x",
                label_en="X",
                data_type="number",
                extra_field="nope",  # type: ignore[call-arg]
            )


# ===========================================================================
# AttributeOptionCreate
# ===========================================================================
class TestAttributeOptionCreate:
    def test_valid(self) -> None:
        m = AttributeOptionCreate(code="ss316", label_en="SS 316", order_index=10)
        assert m.code == "ss316"
        assert m.order_index == 10

    def test_default_order(self) -> None:
        m = AttributeOptionCreate(code="x", label_en="X")
        assert m.order_index == 0

    def test_order_negative_rejected(self) -> None:
        with pytest.raises(ValidationError):
            AttributeOptionCreate(code="x", label_en="X", order_index=-1)


# ===========================================================================
# FamilyAttributeCreate
# ===========================================================================
class TestFamilyAttributeCreate:
    def test_minimal(self) -> None:
        attr_id = uuid4()
        m = FamilyAttributeCreate(
            attribute_id=attr_id,
            group_code="ball_dimensions",
        )
        assert m.attribute_id == attr_id
        assert m.group_code == "ball_dimensions"
        assert m.is_required is False
        assert m.validation_rule is None

    def test_with_validation_rule(self) -> None:
        m = FamilyAttributeCreate(
            attribute_id=uuid4(),
            group_code="ball_general",
            is_required=True,
            validation_rule={"min": 0, "max": 250},
        )
        assert m.validation_rule == {"min": 0, "max": 250}


# ===========================================================================
# AttributeValueBase — discriminated-union-like validators
# ===========================================================================
class TestAttributeValueBaseRequiresOne:
    def test_all_null_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            AttributeValueBase()
        assert "at least one of" in str(exc.value).lower()

    def test_value_number_ok(self) -> None:
        m = AttributeValueBase(value_number=Decimal("12.5"))
        assert m.value_number == Decimal("12.5")

    def test_value_text_ok(self) -> None:
        m = AttributeValueBase(value_text="ss316")
        assert m.value_text == "ss316"

    def test_value_text_empty_rejected(self) -> None:
        # empty string should count as not populated
        with pytest.raises(ValidationError):
            AttributeValueBase(value_text="")

    def test_value_bool_false_ok(self) -> None:
        # False is a valid populated value (not None)
        m = AttributeValueBase(value_bool=False)
        assert m.value_bool is False

    def test_value_enum_id_ok(self) -> None:
        opt = uuid4()
        m = AttributeValueBase(value_enum_id=opt)
        assert m.value_enum_id == opt

    def test_range_min_only_ok(self) -> None:
        m = AttributeValueBase(value_min=Decimal("0"))
        assert m.value_min == Decimal("0")

    def test_range_max_only_ok(self) -> None:
        m = AttributeValueBase(value_max=Decimal("100"))
        assert m.value_max == Decimal("100")

    def test_range_min_greater_than_max_rejected(self) -> None:
        with pytest.raises(ValidationError) as exc:
            AttributeValueBase(value_min=Decimal("10"), value_max=Decimal("5"))
        assert "value_min must be <=" in str(exc.value)


# ===========================================================================
# AttributeValueCreate aliases AttributeValueBase
# ===========================================================================
class TestAttributeValueCreate:
    def test_round_trip_numeric(self) -> None:
        m = AttributeValueCreate(
            value_number=Decimal("50"),
            unit="mm",
            language=None,
        )
        d = m.model_dump()
        assert d["value_number"] == Decimal("50")
        assert d["unit"] == "mm"
        assert d["language"] is None

    def test_invalid_language_length(self) -> None:
        with pytest.raises(ValidationError):
            AttributeValueCreate(value_text="hi", language="eng")


# ===========================================================================
# validate_value_matches_type — service-side mapping
# ===========================================================================
class TestValidateValueMatchesType:
    def test_number_with_number_field_ok(self) -> None:
        m = AttributeValueBase(value_number=Decimal("12"))
        validate_value_matches_type(m, "number")

    def test_number_with_text_field_rejected(self) -> None:
        m = AttributeValueBase(value_text="something")
        with pytest.raises(ValueError) as exc:
            validate_value_matches_type(m, "number")
        assert "value_number" in str(exc.value)

    def test_integer_uses_value_number_field(self) -> None:
        # data_type=integer also maps to value_number column (no separate int col)
        m = AttributeValueBase(value_number=Decimal("3"))
        validate_value_matches_type(m, "integer")

    def test_text_with_text_field_ok(self) -> None:
        m = AttributeValueBase(value_text="some text")
        validate_value_matches_type(m, "text")

    def test_text_with_number_rejected(self) -> None:
        m = AttributeValueBase(value_number=Decimal("1"))
        with pytest.raises(ValueError):
            validate_value_matches_type(m, "text")

    def test_bool_ok(self) -> None:
        m = AttributeValueBase(value_bool=True)
        validate_value_matches_type(m, "bool")

    def test_enum_with_enum_id_ok(self) -> None:
        m = AttributeValueBase(value_enum_id=uuid4())
        validate_value_matches_type(m, "enum")

    def test_enum_without_enum_id_rejected(self) -> None:
        m = AttributeValueBase(value_text="raw_string")
        with pytest.raises(ValueError):
            validate_value_matches_type(m, "enum")

    def test_range_min_max_ok(self) -> None:
        m = AttributeValueBase(value_min=Decimal("0"), value_max=Decimal("10"))
        validate_value_matches_type(m, "range")

    def test_range_min_only_ok(self) -> None:
        m = AttributeValueBase(value_min=Decimal("0"))
        validate_value_matches_type(m, "range")

    def test_dimension_uses_value_number(self) -> None:
        m = AttributeValueBase(value_number=Decimal("100"))
        validate_value_matches_type(m, "dimension")

    def test_extra_field_with_correct_one_rejected(self) -> None:
        # e.g. number type but also text populated → reject
        m = AttributeValueBase(
            value_number=Decimal("1"),
            value_text="extra",
        )
        with pytest.raises(ValueError) as exc:
            validate_value_matches_type(m, "number")
        assert "additional populated fields" in str(exc.value)
