# mt-pricing-backend/tests/unit/importer/test_parser_custom_mapping.py
"""Tests: parse_xlsx_stream con header_row_index y custom_mapping."""
from __future__ import annotations

import io
import openpyxl

from app.services.importer.column_mapper import map_row_with_mapping
from app.services.importer.mapping_detector import ColumnMappingItem
from app.services.importer.parser import parse_xlsx_stream


def _make_xlsx(rows: list[list]) -> io.BytesIO:
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf


def test_parse_with_header_row_index_skips_title_rows():
    """header_row_index=2 salta 2 filas de título."""
    xlsx = _make_xlsx([
        ["PIM CONSOLIDADO"] + [None] * 2,
        ["Generado: 2026-05-13"] + [None] * 2,
        ["SKU", "Familia", "Peso neto (kg)"],
        ["1010", "Valvulas", 0.5],
        ["3015", "Accesorios", 1.2],
    ])
    mapping = [
        ColumnMappingItem("SKU", "sku", "text"),
        ColumnMappingItem("Familia", "family", "text"),
        ColumnMappingItem("Peso neto (kg)", "weight", "decimal"),
    ]
    result = parse_xlsx_stream(xlsx, header_row_index=2, custom_mapping=mapping)
    assert result.header_ok
    assert result.total_data_rows == 2
    assert result.rows[0].sku == "1010"
    assert result.rows[1].sku == "3015"


def test_parse_with_custom_mapping_no_header_validation():
    """Con custom_mapping, no valida contra EXPECTED_HEADERS."""
    xlsx = _make_xlsx([
        ["SKU", "Nueva Columna Inventada", "Familia"],
        ["1010", "valor_x", "Valvulas"],
    ])
    mapping = [
        ColumnMappingItem("SKU", "sku", "text"),
        ColumnMappingItem("Nueva Columna Inventada", "specs.nueva_col", "text"),
        ColumnMappingItem("Familia", "family", "text"),
    ]
    result = parse_xlsx_stream(xlsx, custom_mapping=mapping)
    assert result.header_ok
    assert result.rows[0].sku == "1010"
    assert result.rows[0].payload["specs"]["nueva_col"] == "valor_x"


def test_parse_without_custom_mapping_uses_old_validation():
    """Sin custom_mapping, sigue usando EXPECTED_HEADERS (backward compat)."""
    xlsx = _make_xlsx([
        ["SKU_DESCONOCIDO", "Otra Columna"],
        ["1010", "valor"],
    ])
    result = parse_xlsx_stream(xlsx)  # sin custom_mapping
    # Debe fallar la validación del header (no coincide con EXPECTED_HEADERS).
    assert not result.header_ok
    assert len(result.header_errors) > 0
