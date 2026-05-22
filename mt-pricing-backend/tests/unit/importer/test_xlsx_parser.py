"""Tests para XlsxParser — produce ParsedProduct por fila."""
from __future__ import annotations

import io
from decimal import Decimal

import openpyxl

from app.services.importer.mapping_detector import ColumnMappingItem
from app.services.importer.xlsx_parser import XlsxParser


def _make_xlsx(rows: list[list]) -> bytes:
    """Helper: crea un xlsx en memoria con las filas dadas (primera = header)."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _mapping(*items: tuple[str, str, str]) -> list[ColumnMappingItem]:
    return [ColumnMappingItem(excel_col=e, target_field=t, transform=tr) for e, t, tr in items]


def test_parses_scalar_fields():
    xlsx = _make_xlsx([
        ["sku", "Peso neto (kg)", "Conexión"],
        ["MT-001", 1.5, "Rosca"],
    ])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Peso neto (kg)", "weight", "decimal"),
        ("Conexión", "connection", "text"),
    )
    parser = XlsxParser(xlsx, mapping, header_row_index=0)
    products = list(parser.parse())
    assert len(products) == 1
    p = products[0]
    assert p.sku == "MT-001"
    assert p.scalars["weight"] == Decimal("1.5")
    assert p.scalars["connection"] == "Rosca"


def test_parses_jsonb_dimensions():
    xlsx = _make_xlsx([
        ["sku", "Alto (cm)"],
        ["MT-001", 10.5],
    ])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Alto (cm)", "dimensions.high_mm", "cm_to_mm"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].jsonb["dimensions"]["high_mm"] == "105.0"


def test_parses_translations():
    xlsx = _make_xlsx([
        ["sku", "Nombre EN", "Nombre FR"],
        ["MT-001", "Ball valve", "Robinet à bille"],
    ])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Nombre EN", "translations.en", "text"),
        ("Nombre FR", "translations.fr", "text"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].translations == {"en": "Ball valve", "fr": "Robinet à bille"}


def test_parses_certifications_split_by_comma():
    xlsx = _make_xlsx([
        ["sku", "Certificaciones"],
        ["MT-001", "CE, ISO 9001, WRAS"],
    ])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Certificaciones", "certifications", "text"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].certifications == ["CE", "ISO 9001", "WRAS"]


def test_skips_empty_rows_rows_yielded():
    xlsx = _make_xlsx([["sku"], ["MT-001"], [None], ["MT-002"]])
    mapping = _mapping(("sku", "sku", "text"))
    parser = XlsxParser(xlsx, mapping)
    list(parser.parse())
    assert parser.rows_yielded == 2


def test_empty_sku_rows_yielded():
    xlsx = _make_xlsx([["sku", "Peso"], [None, 1.5]])
    mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))
    parser = XlsxParser(xlsx, mapping)
    list(parser.parse())
    assert parser.rows_yielded == 1


def test_empty_sku_is_error_row():
    xlsx = _make_xlsx([["sku", "Peso"], [None, 1.5]])
    mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))
    products = list(XlsxParser(xlsx, mapping).parse())
    assert len(products) == 1
    assert products[0].is_error_row is True


def test_header_row_index_nonzero():
    xlsx = _make_xlsx([
        ["PIM Export v2"],          # título — fila 0
        ["sku", "Peso"],            # header real — fila 1
        ["MT-001", 0.5],
    ])
    mapping = _mapping(("sku", "sku", "text"), ("Peso", "weight", "decimal"))
    parser = XlsxParser(xlsx, mapping, header_row_index=1)
    products = list(parser.parse())
    assert len(products) == 1
    assert products[0].sku == "MT-001"


def test_skip_target_is_ignored():
    xlsx = _make_xlsx([["sku", "Completitud %"], ["MT-001", 40]])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Completitud %", "_skip", "text"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].scalars.get("_skip") is None
    assert "Completitud %" not in products[0].scalars


def test_unsupported_lang_is_ignored():
    xlsx = _make_xlsx([["sku", "Nombre ZZ"], ["MT-001", "test"]])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Nombre ZZ", "translations.zz", "text"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].translations == {}


def test_parses_jsonb_specs():
    xlsx = _make_xlsx([["sku", "EAN"], ["MT-001", "1234567890123"]])
    mapping = _mapping(("sku", "sku", "text"), ("EAN", "specs.ean_individual", "ean"))
    products = list(XlsxParser(xlsx, mapping).parse())
    assert "ean_individual" in products[0].jsonb["specs"]


def test_parses_jsonb_packaging():
    xlsx = _make_xlsx([["sku", "Qty"], ["MT-001", 6]])
    mapping = _mapping(("sku", "sku", "text"), ("Qty", "packaging.qty_per_box", "int"))
    products = list(XlsxParser(xlsx, mapping).parse())
    assert products[0].jsonb["packaging"]["qty_per_box"] == 6


def test_decimal_stored_as_string_in_jsonb():
    xlsx = _make_xlsx([["sku", "Peso bruto"], ["MT-001", 2.75]])
    mapping = _mapping(
        ("sku", "sku", "text"),
        ("Peso bruto", "specs.weight_gross_kg", "decimal"),
    )
    products = list(XlsxParser(xlsx, mapping).parse())
    val = products[0].jsonb["specs"]["weight_gross_kg"]
    assert isinstance(val, str)
    assert val == "2.75"
