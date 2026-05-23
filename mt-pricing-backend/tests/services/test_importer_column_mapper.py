"""Unit tests para `app.services.importer.column_mapper`.

Sin DB. Cubren:
- Cardinalidad y consistencia del mapping (17 columnas exactas).
- Casts: text/int/decimal/cm_to_mm/ean.
- map_row aplica defaults (brand=MT, family=unclassified, etc.).
- map_row colapsa JSONB buckets (dimensions/packaging/specs).
- map_row reporta errores de cast sin abortar el resto de la fila.
- name_en se deriva de erp_name si no viene explícito.
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.importer.column_mapper import (
    EXCEL_COL_TO_FIELD,
    EXPECTED_HEADERS,
    ImportCastError,
    map_row,
    _cast_cm_to_mm,
    _cast_decimal,
    _cast_ean,
    _cast_int,
    _cast_text,
)


def test_expected_headers_count_matches_spec() -> None:
    """Sprint0 mapping define exactamente 17 columnas."""
    assert len(EXPECTED_HEADERS) == 17
    assert len(EXCEL_COL_TO_FIELD) == 17


def test_expected_headers_first_is_sku() -> None:
    assert EXPECTED_HEADERS[0] == "Referencia de variante"
    spec = EXCEL_COL_TO_FIELD["Referencia de variante"]
    assert spec.target_column == "sku"
    assert spec.nullable is False


def test_cast_text_strips_and_nullifies_empty() -> None:
    assert _cast_text("  hello  ") == "hello"
    assert _cast_text("") is None
    assert _cast_text(None) is None


def test_cast_int_handles_str_float() -> None:
    assert _cast_int("250") == 250
    assert _cast_int("250.0") == 250
    assert _cast_int(180) == 180
    assert _cast_int(None) is None


def test_cast_int_raises_on_garbage() -> None:
    with pytest.raises(ImportCastError):
        _cast_int("abc")


def test_cast_decimal_preserves_precision() -> None:
    assert _cast_decimal("0.0661") == Decimal("0.0661")
    assert _cast_decimal(None) is None


def test_cast_cm_to_mm_multiplies_by_10() -> None:
    assert _cast_cm_to_mm("17") == Decimal("170")
    assert _cast_cm_to_mm("3.8") == Decimal("38.0")


def test_cast_ean_strips_non_digits() -> None:
    assert _cast_ean("8435319100004") == "8435319100004"
    assert _cast_ean(8435319100004) == "8435319100004"
    assert _cast_ean(None) is None


def test_cast_ean_rejects_invalid_length() -> None:
    with pytest.raises(ImportCastError):
        _cast_ean("123")  # 3 digits, no en {8,12,13,14}


def test_map_row_real_pim_first_row() -> None:
    """Reproduce la primera fila real de PIM completo.xlsx."""
    row = (
        "001010",
        "73071910",
        "m-f 90° bend galvanised 3/8”",
        "8435319100004",
        "0.0661",
        "0.0661",
        "4.85",
        "4.85",
        "2.5",
        "28435319100008",
        "250",
        "17",
        "38",
        "26",
        "18435319100001",
        "10",
        "11250",
    )
    payload, errors = map_row(row)
    assert errors == []
    assert payload["sku"] == "001010"
    assert payload["intrastat_code"] == "73071910"
    assert payload["erp_name"].startswith("m-f 90")
    assert payload["weight"] == Decimal("0.0661")
    # JSONB buckets colapsados.
    assert payload["dimensions"] == {
        "high_mm": "4.85",
        "wide_mm": "4.85",
        "deep_mm": "2.5",
    }
    assert payload["packaging"]["qty_per_box"] == 250
    assert payload["packaging"]["box_high_mm"] == "170"  # 17 cm × 10
    assert payload["packaging"]["box_wide_mm"] == "380"
    assert payload["packaging"]["box_deep_mm"] == "260"
    assert payload["packaging"]["moq_inner_box"] == 10
    assert payload["packaging"]["x_pallet"] == 11250
    assert payload["specs"]["ean_individual"] == "8435319100004"
    assert payload["specs"]["ean_box"] == "28435319100008"
    assert payload["specs"]["ean_inner_box"] == "18435319100001"
    assert payload["specs"]["weight_gross_kg"] == "0.0661"
    # Defaults.
    assert payload["brand"] == "MT"
    assert payload["family"] == "unclassified"
    assert payload["data_quality"] == "partial"
    assert payload["active"] is True
    assert payload["manual_locked_fields"] == []
    assert payload["weight_unit"] == "kg"
    # name_en backfill desde erp_name.
    assert payload["name_en"] == payload["erp_name"]


def test_map_row_missing_erp_yields_name_en_error() -> None:
    """Si erp_name está vacío y no se provee name_en, marca error."""
    row = (
        "001010",
        "73071910",
        "",  # erp_name vacío
        "8435319100004",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    )
    payload, errors = map_row(row)
    assert any("name_en" in e for e in errors)


def test_map_row_invalid_int_reports_error_and_continues() -> None:
    """Un cast inválido genera error pero no aborta los demás campos."""
    row = list(
        (
            "001010",
            "73071910",
            "name",
            None,
            None,
            None,
            None,
            None,
            None,
            None,
            "not_an_int",
            None,
            None,
            None,
            None,
            None,
            None,
        )
    )
    payload, errors = map_row(tuple(row))
    assert any("qty x box" in e for e in errors)
    assert payload["sku"] == "001010"  # otros campos sí se setearon
