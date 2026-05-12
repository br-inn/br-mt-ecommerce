"""Unit tests for Wave 2 — lifecycle + technical scalars + parent/child.

Stage 2 (mig 043) movió valve scalars (manufacturing_method, actuator, kv,
kv2, torque_nm, iso5211_interface) y dn_real a `specs` JSONB validados por
JSON Schema. Los tests específicos de esos campos viven ahora en los suites
de spec validators, no aquí.
"""

from __future__ import annotations

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.schemas.products import (
    ALLOWED_LIFECYCLE_STATUS,
    ProductBase,
    ProductPatch,
    ProductResponse,
)


def _base_kwargs(**overrides: object) -> dict[str, object]:
    """Minimal valid ProductBase payload.

    Fase B (mig 065): `name_en` removido de ProductBase — vive en
    product_translations(lang='en'); aquí sólo se incluye `family` como
    obligatorio.
    """
    return {"family": "valve", **overrides}


# ---- ProductBase --------------------------------------------------------------


def test_productbase_default_lifecycle_status() -> None:
    p = ProductBase(**_base_kwargs())
    assert p.lifecycle_status == "active"
    assert p.is_parent is False
    assert p.is_variant is False
    # Fase B (mig 065): `tags` se removió de ProductBase.
    assert not hasattr(p, "tags")


def test_productbase_accepts_all_valid_lifecycle_status() -> None:
    for s in ALLOWED_LIFECYCLE_STATUS:
        ProductBase(**_base_kwargs(lifecycle_status=s))


def test_productbase_rejects_invalid_lifecycle_status() -> None:
    with pytest.raises(ValidationError, match="lifecycle_status"):
        ProductBase(**_base_kwargs(lifecycle_status="zombie"))


def test_productbase_temperature_range_valid() -> None:
    p = ProductBase(**_base_kwargs(temp_min_c=-40, temp_max_c=200))
    assert p.temp_min_c == -40 and p.temp_max_c == 200


def test_productbase_rejects_inverted_temperature_range() -> None:
    with pytest.raises(ValidationError, match="temp_max_c"):
        ProductBase(**_base_kwargs(temp_min_c=100, temp_max_c=50))


def test_productbase_temperature_one_side_only_ok() -> None:
    ProductBase(**_base_kwargs(temp_min_c=-273))
    ProductBase(**_base_kwargs(temp_max_c=2000))


def test_productbase_pressure_decimal() -> None:
    p = ProductBase(**_base_kwargs(pressure_max_bar=Decimal("16.5")))
    assert p.pressure_max_bar == Decimal("16.5")


def test_productbase_pressure_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductBase(**_base_kwargs(pressure_max_bar=Decimal("-1")))


def test_productbase_rejects_legacy_tags() -> None:
    """Fase B (mig 065): tags ya no se acepta en ProductBase (extra='forbid')."""
    with pytest.raises(ValidationError):
        ProductBase(**_base_kwargs(tags=["industrial"]))


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
    # Stage 2 (mig 043) movió valve scalars a specs JSONB; dn_real ≡ dn.
    # Fase 0 (mig 053) dropea image_url/image_status.
    # Fase B (mig 065/066) mantiene `tags` en ProductResponse como
    # default-empty para compat FE; `active` se expone como computed_field.
    expected = {
        "lifecycle_status",
        "revision",
        "series",
        "parent_sku",
        "is_parent",
        "is_variant",
        "size",
        "temp_min_c",
        "temp_max_c",
        "pressure_max_bar",
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
