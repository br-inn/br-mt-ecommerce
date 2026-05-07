"""Unit tests para `app.services.importer_materials.parser` (sin DB)."""

from __future__ import annotations

import io
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.services.importer_materials.parser import parse_materials_xlsx_stream

pytestmark = pytest.mark.unit


def _make_xlsx(header: list, data: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for row in data:
        ws.append(row)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def test_parse_basic_header_and_rows() -> None:
    bio = io.BytesIO(
        _make_xlsx(
            ["producto_descriptor", "temperatura_c", "Acero Inoxidable 316L", "PVC"],
            [
                ["Ácido sulfúrico 98%", 20, "OK", "X"],
                ["Agua destilada", 25, "OK", "OK"],
            ],
        )
    )
    res = parse_materials_xlsx_stream(bio)
    assert res.header_ok
    assert res.materials_columns == ["acero_inoxidable_316l", "pvc"]
    assert res.total_data_rows == 2
    r0 = res.rows[0]
    assert r0.producto_descriptor == "Ácido sulfúrico 98%"
    assert r0.temperatura_c == Decimal("20")
    assert r0.compatibilities["acero_inoxidable_316l"] == "ok"
    assert r0.compatibilities["pvc"] == "x"
    assert r0.ok


def test_parse_empty_compat_cell_skipped() -> None:
    bio = io.BytesIO(
        _make_xlsx(
            ["producto_descriptor", "temperatura_c", "PVC"],
            [["X", 10, ""]],
        )
    )
    res = parse_materials_xlsx_stream(bio)
    r = res.rows[0]
    assert r.ok
    assert r.compatibilities == {}


def test_parse_invalid_temperature_yields_error() -> None:
    bio = io.BytesIO(
        _make_xlsx(
            ["producto_descriptor", "temperatura_c", "PVC"],
            [["A", "abc", "OK"]],
        )
    )
    res = parse_materials_xlsx_stream(bio)
    r = res.rows[0]
    assert not r.ok
    assert any("temperatura_c" in e for e in r.errors)


def test_parse_missing_descriptor_yields_error() -> None:
    bio = io.BytesIO(
        _make_xlsx(
            ["producto_descriptor", "temperatura_c", "PVC"],
            [["", 10, "OK"]],
        )
    )
    res = parse_materials_xlsx_stream(bio)
    r = res.rows[0]
    assert not r.ok
    assert any("producto_descriptor" in e for e in r.errors)


def test_parse_header_mismatch() -> None:
    bio = io.BytesIO(
        _make_xlsx(
            ["wrong_left_header", "temp", "PVC"],
            [["A", 10, "OK"]],
        )
    )
    res = parse_materials_xlsx_stream(bio)
    assert not res.header_ok
    assert any("producto_descriptor" in e for e in res.header_errors)


def test_parse_empty_rows_skipped() -> None:
    bio = io.BytesIO(
        _make_xlsx(
            ["producto_descriptor", "temperatura_c", "PVC"],
            [["A", 10, "OK"], [None, None, None], ["B", 20, "X"]],
        )
    )
    res = parse_materials_xlsx_stream(bio)
    # Empty row in the middle is skipped — total rows = 2.
    assert res.total_data_rows == 2


def test_parse_normalizes_material_headers_with_accents() -> None:
    bio = io.BytesIO(
        _make_xlsx(
            ["producto_descriptor", "temperatura_c", "Cobre/Latón Niquelado"],
            [["A", 10, "OK"]],
        )
    )
    res = parse_materials_xlsx_stream(bio)
    assert res.materials_columns == ["cobre_laton_niquelado"]
