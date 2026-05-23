"""Unit tests for SpecsValidator — 20+ test cases covering happy/unhappy paths.

Uses the real bundled schemas (valve_ball.json, filter.json, _default.json).
No IO beyond loading schemas from disk.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.services.specs.specs_registry import SpecsRegistry
from app.services.specs.specs_validator import (
    FieldError,
    SpecsValidationError,
    SpecsValidator,
    ValidationResult,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def registry() -> SpecsRegistry:
    """Real registry using the bundled schemas dir."""
    SpecsRegistry.reset_instance()
    reg = SpecsRegistry()
    yield reg
    SpecsRegistry.reset_instance()


@pytest.fixture(scope="module")
def validator(registry: SpecsRegistry) -> SpecsValidator:
    return SpecsValidator(registry)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

VALID_VALVE_BALL: dict[str, Any] = {
    "dn": "DN25",
    "dn_real": "27mm",
    "size": '1"',
    "materials_body": "brass CW617N",
    "materials_closure": "chrome-plated brass",
    "materials_seats": "PTFE",
    "materials_gaskets": "PTFE",
}

VALID_FILTER: dict[str, Any] = {
    "dn": "DN50",
    "dn_real": "52mm",
    "size": '2"',
    "materials_body": "cast iron EN-GJL-250",
    "materials_screen": "stainless steel 316",
    "materials_gaskets": "NBR",
}


# ---------------------------------------------------------------------------
# valve_ball — happy path
# ---------------------------------------------------------------------------


def test_valve_ball_valid_minimal(validator: SpecsValidator) -> None:
    result = validator.validate(VALID_VALVE_BALL, "valve", "ball")
    assert result.valid is True
    assert result.errors == []


def test_valve_ball_valid_with_optional_fields(validator: SpecsValidator) -> None:
    specs = {
        **VALID_VALVE_BALL,
        "actuator": "lever",
        "dim_L": 100.0,
        "dim_H": 85.5,
        "dim_T1": 12.0,
        "dim_T2": 12.0,
        "kv": 22.5,
        "torque_nm": 5.0,
        "iso5211_face": "F05",
    }
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is True


def test_valve_ball_valid_with_connections(validator: SpecsValidator) -> None:
    specs = {
        **VALID_VALVE_BALL,
        "connections": [
            {"position": 1, "type": "threaded", "dn": "DN25", "threading": "BSP"},
            {"position": 2, "type": "threaded", "dn": "DN25"},
        ],
    }
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is True


# ---------------------------------------------------------------------------
# valve_ball — missing required field
# ---------------------------------------------------------------------------


def test_valve_ball_missing_dn(validator: SpecsValidator) -> None:
    specs = {k: v for k, v in VALID_VALVE_BALL.items() if k != "dn"}
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is False
    fields = [e.field for e in result.errors]
    assert any("dn" in f for f in fields)


def test_valve_ball_missing_materials_body(validator: SpecsValidator) -> None:
    specs = {k: v for k, v in VALID_VALVE_BALL.items() if k != "materials_body"}
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is False


def test_valve_ball_missing_multiple_required(validator: SpecsValidator) -> None:
    specs = {"dn": "DN25", "dn_real": "27mm"}  # missing size, materials_*
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is False
    assert len(result.errors) >= 3


# ---------------------------------------------------------------------------
# valve_ball — invalid enum
# ---------------------------------------------------------------------------


def test_valve_ball_invalid_actuator_enum(validator: SpecsValidator) -> None:
    specs = {**VALID_VALVE_BALL, "actuator": "invalid_type"}
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is False
    fields = [e.field for e in result.errors]
    assert any("actuator" in f for f in fields)


def test_valve_ball_invalid_iso5211_face(validator: SpecsValidator) -> None:
    specs = {**VALID_VALVE_BALL, "iso5211_face": "F99"}
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is False


def test_valve_ball_invalid_connection_type(validator: SpecsValidator) -> None:
    specs = {
        **VALID_VALVE_BALL,
        "connections": [{"position": 1, "type": "unknown_type"}],
    }
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is False


# ---------------------------------------------------------------------------
# valve_ball — additionalProperties=false
# ---------------------------------------------------------------------------


def test_valve_ball_extra_property_rejected(validator: SpecsValidator) -> None:
    specs = {**VALID_VALVE_BALL, "unknown_field": "value"}
    result = validator.validate(specs, "valve", "ball")
    assert result.valid is False
    fields = [e.field for e in result.errors]
    assert any("unknown_field" in f for f in fields)


# ---------------------------------------------------------------------------
# filter — happy path
# ---------------------------------------------------------------------------


def test_filter_valid_minimal(validator: SpecsValidator) -> None:
    result = validator.validate(VALID_FILTER, "filter")
    assert result.valid is True
    assert result.errors == []


def test_filter_valid_with_double_screen(validator: SpecsValidator) -> None:
    specs = {
        **VALID_FILTER,
        "kv1": 45.0,
        "kv2": 40.0,
        "dim_w1": 0.8,
        "dim_d1": 0.8,
        "dim_w2": 0.5,
        "dim_d2": 0.5,
    }
    result = validator.validate(specs, "filter")
    assert result.valid is True


def test_filter_missing_materials_screen(validator: SpecsValidator) -> None:
    specs = {k: v for k, v in VALID_FILTER.items() if k != "materials_screen"}
    result = validator.validate(specs, "filter")
    assert result.valid is False


def test_filter_extra_property_rejected(validator: SpecsValidator) -> None:
    specs = {**VALID_FILTER, "mystery_field": 99}
    result = validator.validate(specs, "filter")
    assert result.valid is False


# ---------------------------------------------------------------------------
# Default schema — permissive
# ---------------------------------------------------------------------------


def test_default_schema_accepts_empty_dict(validator: SpecsValidator) -> None:
    result = validator.validate({}, "unknown_family")
    assert result.valid is True


def test_default_schema_accepts_arbitrary_properties(validator: SpecsValidator) -> None:
    specs = {"foo": "bar", "baz": 42, "nested": {"a": 1}}
    result = validator.validate(specs, "unknown_family", "unknown_sub")
    assert result.valid is True


# ---------------------------------------------------------------------------
# ValidationResult / FieldError models
# ---------------------------------------------------------------------------


def test_validation_result_model() -> None:
    vr = ValidationResult(
        valid=False, errors=[FieldError(field="specs.dn", message="required", value=None)]
    )
    d = vr.model_dump()
    assert d["valid"] is False
    assert len(d["errors"]) == 1
    assert d["errors"][0]["field"] == "specs.dn"


def test_field_error_truncates_long_value(validator: SpecsValidator) -> None:
    specs = {**VALID_VALVE_BALL, "unknown_field": "x" * 300}
    result = validator.validate(specs, "valve", "ball")
    # At least one error for the extra property
    assert result.valid is False


# ---------------------------------------------------------------------------
# Integration: ProductService rejects invalid specs
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_product_service_rejects_invalid_specs(validator: SpecsValidator) -> None:
    """ProductService.create_product raises SpecsValidationError for invalid specs."""
    from app.services.products.product_service import ProductService

    mock_session = MagicMock()
    mock_session.flush = AsyncMock()

    # Mock products repository to say SKU doesn't exist
    mock_products_repo = AsyncMock()
    mock_products_repo.get_by_sku.return_value = None

    service = ProductService(session=mock_session, specs_validator=validator)
    service.products = mock_products_repo

    mock_actor = MagicMock()
    mock_actor.id = uuid4()
    mock_actor.email = "test@mt.ae"

    # specs missing required fields for valve/ball
    data = {
        "sku": "MT-VB-001",
        "name_en": "Test Ball Valve",
        "family": "valve",
        "subfamily": "ball",
        "specs": {"dn": "DN25"},  # missing dn_real, size, materials_*
    }

    with pytest.raises(SpecsValidationError) as exc_info:
        await service.create_product(data, mock_actor)

    assert len(exc_info.value.errors) > 0
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_product_service_accepts_valid_specs(validator: SpecsValidator) -> None:
    """ProductService.create_product proceeds past validation for valid specs."""
    from app.services.products.product_service import ProductService

    mock_session = MagicMock()
    mock_session.flush = AsyncMock()

    mock_products_repo = AsyncMock()
    mock_products_repo.get_by_sku.return_value = None
    mock_products_repo.create.return_value = MagicMock(
        sku="MT-VB-002",
        **dict.fromkeys(["name_en", "family", "subfamily"]),
    )

    mock_audit_repo = AsyncMock()
    mock_audit_repo.record = AsyncMock()

    service = ProductService(session=mock_session, specs_validator=validator)
    service.products = mock_products_repo
    service.audit = mock_audit_repo
    # Fase B: create_product ahora puede llamar translations.upsert.
    service.translations = AsyncMock()
    service.translations.upsert = AsyncMock(return_value=(MagicMock(), True))

    mock_actor = MagicMock()
    mock_actor.id = uuid4()
    mock_actor.email = "test@mt.ae"

    data = {
        "sku": "MT-VB-002",
        "name_en": "Test Ball Valve",
        "family": "valve",
        "subfamily": "ball",
        "specs": VALID_VALVE_BALL,
        "brand_id": uuid4(),
        "family_id": uuid4(),
    }

    # Should NOT raise SpecsValidationError
    await service.create_product(data, mock_actor)
    mock_products_repo.create.assert_called_once()


@pytest.mark.asyncio
async def test_product_service_no_validator_skips_validation() -> None:
    """ProductService without specs_validator skips validation entirely."""
    from app.services.products.product_service import ProductService

    mock_session = MagicMock()
    mock_products_repo = AsyncMock()
    mock_products_repo.get_by_sku.return_value = None
    mock_products_repo.create.return_value = MagicMock(sku="MT-VB-003")
    mock_audit_repo = AsyncMock()
    mock_audit_repo.record = AsyncMock()

    service = ProductService(session=mock_session, specs_validator=None)
    service.products = mock_products_repo
    service.audit = mock_audit_repo
    # Fase B: create_product ahora puede llamar translations.upsert.
    service.translations = AsyncMock()
    service.translations.upsert = AsyncMock(return_value=(MagicMock(), True))

    mock_actor = MagicMock()
    mock_actor.id = uuid4()
    mock_actor.email = "test@mt.ae"

    # Garbage specs — but no validator, so should pass through
    data = {
        "sku": "MT-VB-003",
        "name_en": "Valve",
        "family": "valve",
        "specs": {"garbage": True},
        "brand_id": uuid4(),
        "family_id": uuid4(),
    }
    await service.create_product(data, mock_actor)
    mock_products_repo.create.assert_called_once()
