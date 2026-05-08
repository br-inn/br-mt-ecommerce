"""Unit tests for Wave 6 — tech_tables schemas (per-kind data validation)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.tech_tables import (
    DimensionsByDnData,
    MaterialsMatrixData,
    PressureTemperatureData,
    ProductTechTableCreate,
    ProductTechTablePatch,
    ProductTechTableResponse,
)


# ---- materials_matrix ----------------------------------------------------------

def test_materials_matrix_happy() -> None:
    data = {
        "rows": [
            {"component": "body", "material": "brass"},
            {"component": "seat", "material": "ptfe", "observations": "FDA"},
        ]
    }
    p = ProductTechTableCreate(kind="materials_matrix", data=data)
    assert p.kind == "materials_matrix"


def test_materials_matrix_missing_required_field() -> None:
    with pytest.raises(ValidationError):
        ProductTechTableCreate(
            kind="materials_matrix", data={"rows": [{"material": "brass"}]}
        )


def test_materials_matrix_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        MaterialsMatrixData.model_validate(
            {"rows": [{"component": "body", "material": "brass", "extra": "no"}]}
        )


# ---- dimensions_by_dn ----------------------------------------------------------

def test_dimensions_by_dn_happy_with_columns() -> None:
    data = {
        "columns": ["L", "H", "K"],
        "rows": [
            {"dn": "DN15", "measures": {"L": 50.0, "H": 30.0, "K": 14.0}},
            {"dn": "DN20", "measures": {"L": 60.0, "H": 35.0, "K": 16.0}},
        ],
    }
    ProductTechTableCreate(kind="dimensions_by_dn", data=data)


def test_dimensions_by_dn_unknown_measure_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductTechTableCreate(
            kind="dimensions_by_dn",
            data={
                "columns": ["L", "H"],
                "rows": [{"dn": "DN15", "measures": {"L": 50.0, "X": 9.0}}],
            },
        )


def test_dimensions_by_dn_no_columns_allows_any_measures() -> None:
    DimensionsByDnData.model_validate(
        {"columns": [], "rows": [{"dn": "DN15", "measures": {"anything": 1.0}}]}
    )


def test_dimensions_by_dn_null_measure_value_ok() -> None:
    DimensionsByDnData.model_validate(
        {"columns": ["L"], "rows": [{"dn": "DN15", "measures": {"L": None}}]}
    )


# ---- pressure_temperature ------------------------------------------------------

def test_pressure_temperature_happy() -> None:
    data = {
        "points": [
            {"temp_c": -20, "pressure_max_bar": 16.0},
            {"temp_c": 20, "pressure_max_bar": 16.0},
            {"temp_c": 80, "pressure_max_bar": 12.0},
        ],
        "notes": "EN 1092-1 PN16",
    }
    ProductTechTableCreate(kind="pressure_temperature", data=data)


def test_pressure_temperature_negative_pressure_rejected() -> None:
    with pytest.raises(ValidationError):
        PressureTemperatureData.model_validate(
            {"points": [{"temp_c": 0, "pressure_max_bar": -1.0}]}
        )


def test_pressure_temperature_temp_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        PressureTemperatureData.model_validate(
            {"points": [{"temp_c": 9999, "pressure_max_bar": 1.0}]}
        )


# ---- generic ------------------------------------------------------------------

def test_create_invalid_kind_rejected() -> None:
    with pytest.raises(ValidationError):
        ProductTechTableCreate(kind="unknown", data={})


def test_create_default_schema_version_v1() -> None:
    p = ProductTechTableCreate(kind="materials_matrix", data={"rows": []})
    assert p.schema_version == "v1"
    assert p.source == "manual"


def test_patch_partial_ok() -> None:
    p = ProductTechTablePatch(notes="updated")
    assert p.notes == "updated"


def test_response_fields() -> None:
    fields = set(ProductTechTableResponse.model_fields.keys())
    assert {
        "id",
        "product_sku",
        "kind",
        "schema_version",
        "source",
        "data",
        "source_asset_id",
        "notes",
        "created_at",
        "updated_at",
    } <= fields
