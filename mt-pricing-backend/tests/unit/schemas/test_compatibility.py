"""Unit tests para schemas de compatibilidad (Pydantic V2).

Cobertura:
1.  CompatibilityKind tiene los 5 valores esperados.
2.  ProductCompatibilityCreate válido con todos los campos.
3.  ProductCompatibilityCreate rechaza extra fields.
4.  ProductCompatibilityCreate requiere min_length en compatible_with_sku.
5.  ProductCompatibilityCreate position fuera de rango → error.
6.  ProductCompatibilityResponse se construye desde dict (from_attributes=False ok).
7.  CompatibleProductSummary desnormalizado.
8.  ProductCompatibilityPatch acepta solo notes o solo position.
9.  ProductCompatibilityReplaceItem es válido en lista.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.schemas.compatibility import (
    CompatibilityKind,
    CompatibilityOwnerType,
    CompatibleProductSummary,
    ProductCompatibilityCreate,
    ProductCompatibilityPatch,
    ProductCompatibilityReplaceItem,
    ProductCompatibilityResponse,
)

pytestmark = pytest.mark.unit


def test_compatibility_kind_values() -> None:
    assert set(k.value for k in CompatibilityKind) == {
        "spare_part",
        "accessory",
        "replaces",
        "replaced_by",
        "compatible_with",
    }


def test_create_valid_full() -> None:
    obj = ProductCompatibilityCreate(
        compatible_with_sku="MT-B-002",
        kind=CompatibilityKind.spare_part,
        notes="Seal kit",
        position=1,
    )
    assert obj.compatible_with_sku == "MT-B-002"
    assert obj.notes == "Seal kit"
    assert obj.position == 1


def test_create_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError) as exc_info:
        ProductCompatibilityCreate(  # type: ignore[call-arg]
            compatible_with_sku="MT-B-002",
            kind="spare_part",
            unknown_field="bad",
        )
    assert "extra_forbidden" in str(exc_info.value) or "unexpected" in str(exc_info.value).lower()


def test_create_sku_too_short() -> None:
    with pytest.raises(ValidationError):
        ProductCompatibilityCreate(compatible_with_sku="XY", kind="spare_part")


def test_create_position_out_of_range() -> None:
    with pytest.raises(ValidationError):
        ProductCompatibilityCreate(
            compatible_with_sku="MT-B-002",
            kind="spare_part",
            position=40000,  # > 32767
        )


def test_response_from_dict() -> None:
    uid = uuid4()
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)
    obj = ProductCompatibilityResponse(
        id=uid,
        product_sku="MT-A-001",
        compatible_with_sku="MT-B-002",
        kind=CompatibilityKind.accessory,
        notes=None,
        position=0,
        created_at=now,
        created_by=None,
        compatible_product=None,
    )
    assert obj.id == uid
    assert obj.kind == CompatibilityKind.accessory


def test_compatible_product_summary() -> None:
    summary = CompatibleProductSummary(
        sku="MT-B-002",
        name_en="Valve B",
        family="valves",
        primary_image_url="products/MT-B-002/main.jpg",
    )
    assert summary.primary_image_url == "products/MT-B-002/main.jpg"


def test_patch_partial_notes_only() -> None:
    patch = ProductCompatibilityPatch(notes="Updated note")
    assert patch.notes == "Updated note"
    assert patch.position is None


def test_patch_partial_position_only() -> None:
    patch = ProductCompatibilityPatch(position=5)
    assert patch.position == 5
    assert patch.notes is None


def test_replace_item_valid() -> None:
    items = [
        ProductCompatibilityReplaceItem(
            compatible_with_sku="MT-C-003",
            kind=CompatibilityKind.compatible_with,
        ),
        ProductCompatibilityReplaceItem(
            compatible_with_sku="MT-D-004",
            kind=CompatibilityKind.replaces,
            position=2,
        ),
    ]
    assert len(items) == 2
    assert items[0].position == 0
    assert items[1].position == 2


# ---------------------------------------------------------------------------
# Fase 5 — owner_type + DN range tests
# ---------------------------------------------------------------------------


def test_owner_type_enum_values() -> None:
    """CompatibilityOwnerType expone product/variant/series."""
    assert {o.value for o in CompatibilityOwnerType} == {
        "product",
        "variant",
        "series",
    }


def test_create_defaults_owner_type_product() -> None:
    """Sin owner_type → default 'product' (compat con clientes legacy)."""
    obj = ProductCompatibilityCreate(
        compatible_with_sku="MT-B-002",
        kind=CompatibilityKind.spare_part,
    )
    assert obj.owner_type == CompatibilityOwnerType.product
    assert obj.dn_min is None
    assert obj.dn_max is None


def test_create_with_series_owner_and_dn_range() -> None:
    """Crea recambio polymorphic vinculado a una serie con rango DN 15..50."""
    obj = ProductCompatibilityCreate(
        compatible_with_sku="MT-KIT-001",
        kind=CompatibilityKind.spare_part,
        owner_type=CompatibilityOwnerType.series,
        dn_min=15,
        dn_max=50,
    )
    assert obj.owner_type == CompatibilityOwnerType.series
    assert obj.dn_min == 15
    assert obj.dn_max == 50


def test_create_dn_max_less_than_min_rejected() -> None:
    """dn_max < dn_min → ValidationError."""
    with pytest.raises(ValidationError):
        ProductCompatibilityCreate(
            compatible_with_sku="MT-KIT-002",
            kind=CompatibilityKind.spare_part,
            dn_min=50,
            dn_max=15,
        )


def test_create_dn_only_min_allowed() -> None:
    """Solo dn_min sin dn_max → válido (semi-acotado ≥ dn_min)."""
    obj = ProductCompatibilityCreate(
        compatible_with_sku="MT-KIT-003",
        kind=CompatibilityKind.spare_part,
        dn_min=25,
    )
    assert obj.dn_min == 25
    assert obj.dn_max is None


def test_create_dn_negative_rejected() -> None:
    """dn_min negativo → ValidationError (ge=0)."""
    with pytest.raises(ValidationError):
        ProductCompatibilityCreate(
            compatible_with_sku="MT-KIT-004",
            kind=CompatibilityKind.spare_part,
            dn_min=-1,
        )


def test_replace_item_carries_owner_type_and_dn() -> None:
    """ProductCompatibilityReplaceItem propaga owner_type + dn_min/dn_max."""
    item = ProductCompatibilityReplaceItem(
        compatible_with_sku="MT-KIT-005",
        kind=CompatibilityKind.spare_part,
        owner_type=CompatibilityOwnerType.series,
        dn_min=20,
        dn_max=40,
    )
    assert item.owner_type == CompatibilityOwnerType.series
    assert item.dn_min == 20
    assert item.dn_max == 40


def test_response_includes_owner_type_and_dn() -> None:
    """ProductCompatibilityResponse expone owner_type + dn_min/dn_max."""
    uid = uuid4()
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)
    obj = ProductCompatibilityResponse(
        id=uid,
        product_sku="series-pn40",
        compatible_with_sku="MT-KIT-006",
        kind=CompatibilityKind.spare_part,
        position=0,
        owner_type=CompatibilityOwnerType.series,
        dn_min=15,
        dn_max=100,
        created_at=now,
    )
    assert obj.owner_type == CompatibilityOwnerType.series
    assert obj.dn_min == 15
    assert obj.dn_max == 100


def test_response_defaults_owner_type_product_when_missing() -> None:
    """Compat: response sin owner_type explícito asume 'product'."""
    uid = uuid4()
    from datetime import datetime, timezone

    now = datetime.now(tz=timezone.utc)
    obj = ProductCompatibilityResponse(
        id=uid,
        product_sku="MT-A-001",
        compatible_with_sku="MT-B-002",
        kind=CompatibilityKind.spare_part,
        position=0,
        created_at=now,
    )
    assert obj.owner_type == CompatibilityOwnerType.product
    assert obj.dn_min is None
    assert obj.dn_max is None
