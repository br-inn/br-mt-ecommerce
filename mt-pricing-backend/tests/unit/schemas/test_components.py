"""Unit tests for Wave 3 — components (materials + connections) schemas."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.components import (
    ProductConnectionCreate,
    ProductConnectionPatch,
    ProductConnectionResponse,
    ProductConnectionsReplaceRequest,
    ProductMaterialCreate,
    ProductMaterialPatch,
    ProductMaterialResponse,
    ProductMaterialsReplaceRequest,
)


# ---- ProductMaterial ----------------------------------------------------------

def test_material_create_happy() -> None:
    m = ProductMaterialCreate(component="body", position=0, material="stainless_steel_316l")
    assert m.component == "body"
    assert m.material == "stainless_steel_316l"
    assert m.observations is None


def test_material_default_position_is_zero() -> None:
    m = ProductMaterialCreate(component="seat", material="ptfe")
    assert m.position == 0


def test_material_position_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductMaterialCreate(component="body", position=-1, material="brass")


def test_material_invalid_component_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductMaterialCreate(component="UNICORN", position=0, material="brass")


def test_material_strip_whitespace() -> None:
    m = ProductMaterialCreate(component="body", material="  stainless_steel  ")
    assert m.material == "stainless_steel"


def test_material_observations_optional_with_max() -> None:
    m = ProductMaterialCreate(
        component="gasket", material="epdm", observations="food-safe certified"
    )
    assert m.observations == "food-safe certified"
    with pytest.raises(ValidationError):
        ProductMaterialCreate(component="gasket", material="epdm", observations="x" * 600)


def test_material_patch_partial() -> None:
    p = ProductMaterialPatch(material="copper")
    assert p.material == "copper"


def test_materials_replace_request_max_64() -> None:
    items = [
        ProductMaterialCreate(component="body", position=i, material="stainless_steel")
        for i in range(64)
    ]
    ProductMaterialsReplaceRequest(items=items)
    with pytest.raises(ValidationError):
        ProductMaterialsReplaceRequest(items=items + [items[0]])


def test_materials_replace_empty_array_ok() -> None:
    ProductMaterialsReplaceRequest(items=[])


# ---- ProductConnection --------------------------------------------------------

def test_connection_create_happy() -> None:
    c = ProductConnectionCreate(
        position=1,
        connection_type="flange",
        dn="DN50",
        size="4inch",
    )
    assert c.position == 1
    assert c.connection_type == "flange"


def test_connection_position_must_be_one_or_more() -> None:
    with pytest.raises(ValidationError):
        ProductConnectionCreate(position=0, connection_type="flange")


def test_connection_position_max_eight() -> None:
    ProductConnectionCreate(position=8, connection_type="threaded")
    with pytest.raises(ValidationError):
        ProductConnectionCreate(position=9, connection_type="threaded")


def test_connection_invalid_type_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductConnectionCreate(position=1, connection_type="magnetic")


def test_connection_threading_optional() -> None:
    c = ProductConnectionCreate(
        position=1, connection_type="threaded", threading="BSP"
    )
    assert c.threading == "BSP"


def test_connection_patch_partial() -> None:
    p = ProductConnectionPatch(connection_type="weld")
    assert p.connection_type == "weld"


def test_connections_replace_request_max_8() -> None:
    items = [
        ProductConnectionCreate(position=i, connection_type="flange") for i in range(1, 9)
    ]
    ProductConnectionsReplaceRequest(items=items)
    with pytest.raises(ValidationError):
        ProductConnectionsReplaceRequest(
            items=items
            + [ProductConnectionCreate(position=9, connection_type="flange")]
        )


# ---- Response shape -----------------------------------------------------------

def test_response_models_have_expected_fields() -> None:
    mat_fields = set(ProductMaterialResponse.model_fields.keys())
    assert {"product_sku", "component", "position", "material", "observations", "created_at", "updated_at"} <= mat_fields

    conn_fields = set(ProductConnectionResponse.model_fields.keys())
    assert {
        "product_sku",
        "position",
        "connection_type",
        "dn",
        "dn_real",
        "size",
        "threading",
        "notes",
        "created_at",
        "updated_at",
    } <= conn_fields
