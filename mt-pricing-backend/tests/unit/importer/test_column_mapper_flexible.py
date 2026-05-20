# mt-pricing-backend/tests/unit/importer/test_column_mapper_flexible.py
"""Tests para map_row_with_mapping (mapeo flexible)."""
from __future__ import annotations

from decimal import Decimal

from app.services.importer.column_mapper import map_row_with_mapping
from app.services.importer.mapping_detector import ColumnMappingItem


def _mapping(*items: tuple[str, str, str]) -> list[ColumnMappingItem]:
    return [ColumnMappingItem(excel_col=e, target_field=t, transform=tr)
            for e, t, tr in items]


def test_maps_scalar_fields():
    headers = ["SKU", "Familia", "Peso neto (kg)"]
    row = ("1010", "Valvulas", 0.5)
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Familia", "family", "text"),
        ("Peso neto (kg)", "weight", "decimal"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert payload["sku"] == "1010"
    assert payload["family"] == "Valvulas"
    assert payload["weight"] == Decimal("0.5")
    assert errors == []


def test_maps_jsonb_dimensions_with_cm_to_mm():
    headers = ["SKU", "Alto pieza (cm)", "Ancho pieza (cm)"]
    row = ("1010", 10.5, 5.0)
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Alto pieza (cm)", "dimensions.high_mm", "cm_to_mm"),
        ("Ancho pieza (cm)", "dimensions.wide_mm", "cm_to_mm"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert payload["dimensions"]["high_mm"] == "105.0"
    assert payload["dimensions"]["wide_mm"] == "50.0"
    assert errors == []


def test_jsonb_values_are_json_serializable():
    """Los valores JSONB deben ser serializables por json.dumps (sin Decimal)."""
    import json
    headers = ["SKU", "Alto pieza (cm)"]
    row = ("1010", 10.5)
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Alto pieza (cm)", "dimensions.high_mm", "cm_to_mm"),
    )
    payload, _ = map_row_with_mapping(row, headers, mapping)
    # Must not raise TypeError
    serialized = json.dumps(payload)
    assert '"high_mm"' in serialized


def test_maps_specs_arbitrary_key():
    headers = ["SKU", "EAN unidad"]
    row = ("1010", "1234567890123")
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("EAN unidad", "specs.ean_individual", "ean"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert payload["specs"]["ean_individual"] == "1234567890123"


def test_skip_columns_are_ignored():
    headers = ["SKU", "Completitud %", "En PIM"]
    row = ("1010", 40, "✓")
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Completitud %", "_skip", "text"),
        ("En PIM", "specs.en_pim", "bool_check"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert "Completitud %" not in str(payload)
    assert payload["specs"]["en_pim"] is True


def test_bool_check_transform():
    headers = ["SKU", "En PIM"]
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("En PIM", "specs.en_pim", "bool_check"),
    )
    for val, expected in [("✓", True), ("yes", True), ("1", True), (None, False), ("", False)]:
        row = ("1010", val)
        payload, _ = map_row_with_mapping(row, headers, mapping)
        assert payload["specs"]["en_pim"] is expected, f"val={val!r}"


def test_percent_transform():
    headers = ["SKU", "Completitud %"]
    row = ("1010", 40)
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Completitud %", "specs.completitud_pct", "percent"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert payload["specs"]["completitud_pct"] == 40
    assert errors == []


def test_percent_out_of_range_raises_error():
    """Porcentaje fuera de rango [0,100] genera error de fila."""
    headers = ["SKU", "Completitud %"]
    row = ("1010", 150)
    mapping = _mapping(
        ("SKU", "sku", "text"),
        ("Completitud %", "specs.completitud_pct", "percent"),
    )
    payload, errors = map_row_with_mapping(row, headers, mapping)
    assert len(errors) == 1
    assert "fuera de rango" in errors[0]
