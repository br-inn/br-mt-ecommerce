"""Unit tests for Wave 2 — lifecycle + technical scalars + parent/child."""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.products import (
    ALLOWED_ACTUATOR,
    ALLOWED_LIFECYCLE_STATUS,
    ALLOWED_MANUFACTURING_METHOD,
    ProductBase,
    ProductPatch,
    ProductResponse,
)


def _base_kwargs(**overrides: object) -> dict[str, object]:
    """Minimal valid ProductBase payload."""
    return {"name_en": "Test", "family": "valve", **overrides}


# ---- ProductBase --------------------------------------------------------------


def test_productbase_default_lifecycle_status() -> None:
    p = ProductBase(**_base_kwargs())
    assert p.lifecycle_status == "active"
    assert p.is_parent is False
    assert p.is_variant is False
    assert p.tags == []


def test_productbase_accepts_all_valid_lifecycle_status() -> None:
    for s in ALLOWED_LIFECYCLE_STATUS:
        ProductBase(**_base_kwargs(lifecycle_status=s))


def test_productbase_rejects_invalid_lifecycle_status() -> None:
    with pytest.raises(ValidationError, match="lifecycle_status"):
        ProductBase(**_base_kwargs(lifecycle_status="zombie"))


def test_productbase_validates_manufacturing_method_lowercased() -> None:
    p = ProductBase(**_base_kwargs(manufacturing_method="FORGED"))
    assert p.manufacturing_method == "forged"


def test_productbase_rejects_unknown_manufacturing_method() -> None:
    with pytest.raises(ValidationError, match="manufacturing_method"):
        ProductBase(**_base_kwargs(manufacturing_method="alchemy"))


def test_productbase_validates_actuator_lowercased() -> None:
    for actuator in ALLOWED_ACTUATOR:
        ProductBase(**_base_kwargs(actuator=actuator.upper()))


def test_productbase_rejects_unknown_actuator() -> None:
    with pytest.raises(ValidationError, match="actuator"):
        ProductBase(**_base_kwargs(actuator="psychic"))


def test_productbase_temperature_range_valid() -> None:
    p = ProductBase(**_base_kwargs(temp_min_c=-40, temp_max_c=200))
    assert p.temp_min_c == -40 and p.temp_max_c == 200


def test_productbase_rejects_inverted_temperature_range() -> None:
    with pytest.raises(ValidationError, match="temp_max_c"):
        ProductBase(**_base_kwargs(temp_min_c=100, temp_max_c=50))


def test_productbase_temperature_one_side_only_ok() -> None:
    ProductBase(**_base_kwargs(temp_min_c=-273))
    ProductBase(**_base_kwargs(temp_max_c=2000))


def test_productbase_pressure_kv_torque_decimals() -> None:
    p = ProductBase(
        **_base_kwargs(
            pressure_max_bar=Decimal("16.5"),
            kv=Decimal("0.85"),
            kv2=Decimal("0.42"),
            torque_nm=Decimal("125.50"),
        )
    )
    assert p.pressure_max_bar == Decimal("16.5")
    assert p.kv == Decimal("0.85")


def test_productbase_pressure_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductBase(**_base_kwargs(pressure_max_bar=Decimal("-1")))


def test_productbase_iso5211_interface_string() -> None:
    p = ProductBase(**_base_kwargs(iso5211_interface="F05"))
    assert p.iso5211_interface == "F05"


def test_productbase_tags_array() -> None:
    p = ProductBase(**_base_kwargs(tags=["industrial", "hot-water"]))
    assert "industrial" in p.tags


def test_productbase_video_url_optional() -> None:
    p = ProductBase(**_base_kwargs(video_url="https://youtu.be/abc"))
    assert p.video_url == "https://youtu.be/abc"


def test_productbase_parent_sku_field_present() -> None:
    p = ProductBase(**_base_kwargs(parent_sku="MTV-100", is_variant=True))
    assert p.parent_sku == "MTV-100"
    assert p.is_variant is True


# ---- ProductPatch -------------------------------------------------------------


def test_productpatch_partial_update_lifecycle() -> None:
    p = ProductPatch(lifecycle_status="deprecated")
    assert p.lifecycle_status == "deprecated"


def test_productpatch_rejects_invalid_lifecycle() -> None:
    with pytest.raises(ValidationError, match="lifecycle_status"):
        ProductPatch(lifecycle_status="banana")


def test_productpatch_temp_range_validated() -> None:
    with pytest.raises(ValidationError, match="temp_max_c"):
        ProductPatch(temp_min_c=200, temp_max_c=100)


def test_productpatch_at_least_one_field_required() -> None:
    with pytest.raises(ValidationError, match="vacío"):
        ProductPatch()


# ---- ProductResponse ----------------------------------------------------------


def test_productresponse_includes_wave2_fields() -> None:
    fields = set(ProductResponse.model_fields.keys())
    expected = {
        "lifecycle_status",
        "revision",
        "series",
        "parent_sku",
        "is_parent",
        "is_variant",
        "dn_real",
        "size",
        "temp_min_c",
        "temp_max_c",
        "pressure_max_bar",
        "manufacturing_method",
        "actuator",
        "kv",
        "kv2",
        "torque_nm",
        "iso5211_interface",
        "tags",
        "video_url",
        "external_url",
    }
    missing = expected - fields
    assert missing == set(), f"missing in ProductResponse: {missing}"


def test_productresponse_lifecycle_default_active() -> None:
    # When constructing without DB row context, default applies.
    fields = ProductResponse.model_fields
    assert fields["lifecycle_status"].default == "active"
    assert fields["is_parent"].default is False
    assert fields["is_variant"].default is False


# ---- Allowed sets --------------------------------------------------------------


def test_allowed_sets_have_expected_size() -> None:
    assert len(ALLOWED_LIFECYCLE_STATUS) == 5
    assert len(ALLOWED_MANUFACTURING_METHOD) >= 6
    assert len(ALLOWED_ACTUATOR) >= 6
