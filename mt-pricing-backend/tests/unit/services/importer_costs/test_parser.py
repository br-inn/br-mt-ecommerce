"""Unit tests para `app.services.importer_costs.parser` (sin DB).

Construye xlsx en memoria con openpyxl y verifica:
- Header válido aceptado.
- Header inválido reporta header_errors.
- Casts correctos (Decimal/datetime/text).
- Detección de duplicados (sku, scheme, supplier).
- Filas con total faltante o no numérico → errors.
"""

from __future__ import annotations

import io
from datetime import date
from decimal import Decimal

import pytest
from openpyxl import Workbook

from app.services.importer_costs.parser import (
    EXPECTED_COSTS_HEADERS,
    parse_costs_xlsx_stream,
)

pytestmark = pytest.mark.unit


def _make_xlsx(rows: list[list]) -> bytes:
    """Crea un xlsx en memoria con header + filas de datos."""
    wb = Workbook()
    ws = wb.active
    ws.append(list(EXPECTED_COSTS_HEADERS))
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _row(
    sku="SKU001",
    scheme="FBA",
    supplier="SUP-A",
    currency="EUR",
    total="100.50",
    fob="80",
    freight="10",
    customs="5",
    fba="3",
    fbm="0",
    pay="1",
    mkt="0.5",
    storage="0.5",
    ppc="0",
    otros="0.5",
    valid_from="2026-05-07",
):
    return [
        sku,
        scheme,
        supplier,
        currency,
        total,
        fob,
        freight,
        customs,
        fba,
        fbm,
        pay,
        mkt,
        storage,
        ppc,
        otros,
        valid_from,
    ]


def test_parse_valid_basic_row() -> None:
    bio = io.BytesIO(_make_xlsx([_row()]))
    res = parse_costs_xlsx_stream(bio)
    assert res.header_ok, res.header_errors
    assert res.total_data_rows == 1
    r = res.rows[0]
    assert r.ok, r.errors
    assert r.sku == "SKU001"
    assert r.scheme_code == "FBA"
    assert r.supplier_code == "SUP-A"
    assert r.currency == "EUR"
    assert r.total == Decimal("100.50")
    assert r.breakdown["fob"] == "80"
    assert r.breakdown["freight"] == "10"
    assert r.valid_from == date(2026, 5, 7)
    assert isinstance(r.valid_from, date)


def test_parse_header_mismatch() -> None:
    wb = Workbook()
    ws = wb.active
    ws.append(["wrong", "headers", "x"])
    ws.append(["a", "b", "c"])
    bio = io.BytesIO()
    wb.save(bio)
    bio.seek(0)
    res = parse_costs_xlsx_stream(bio)
    assert not res.header_ok
    assert len(res.header_errors) > 0


def test_parse_total_missing_yields_error() -> None:
    bio = io.BytesIO(_make_xlsx([_row(total="")]))
    res = parse_costs_xlsx_stream(bio)
    r = res.rows[0]
    assert not r.ok
    assert any("'total'" in e for e in r.errors)


def test_parse_total_non_numeric_yields_error() -> None:
    bio = io.BytesIO(_make_xlsx([_row(total="abc")]))
    res = parse_costs_xlsx_stream(bio)
    r = res.rows[0]
    assert not r.ok
    assert any("Decimal inválido" in e or "'total'" in e for e in r.errors)


def test_parse_negative_total_rejected() -> None:
    bio = io.BytesIO(_make_xlsx([_row(total="-10")]))
    res = parse_costs_xlsx_stream(bio)
    r = res.rows[0]
    assert not r.ok
    assert any(">= 0" in e for e in r.errors)


def test_parse_duplicate_keys_marked_in_second_occurrence() -> None:
    bio = io.BytesIO(
        _make_xlsx(
            [
                _row(sku="A", scheme="FBA", supplier="S1", total="1"),
                _row(sku="A", scheme="FBA", supplier="S1", total="2"),  # dup
                _row(sku="A", scheme="FBM", supplier="S1", total="3"),  # diff scheme
            ]
        )
    )
    res = parse_costs_xlsx_stream(bio)
    assert len(res.duplicate_keys) == 1
    assert res.duplicate_keys[0] == ("A", "FBA", "S1")
    # The second row should have an error.
    second_row = res.rows[1]
    assert any("Duplicado" in e for e in second_row.errors)
    # Third row (different scheme) should be ok.
    third = res.rows[2]
    assert third.ok


def test_parse_currency_invalid_length_rejected() -> None:
    bio = io.BytesIO(_make_xlsx([_row(currency="ABCD")]))
    res = parse_costs_xlsx_stream(bio)
    r = res.rows[0]
    assert any("currency" in e for e in r.errors)


def test_parse_valid_from_absent_defaults_to_today() -> None:
    """Si la fila no trae valid_from, se usa la fecha de hoy (documentado)."""
    bio = io.BytesIO(_make_xlsx([_row(valid_from="")]))
    res = parse_costs_xlsx_stream(bio)
    r = res.rows[0]
    assert r.ok
    assert r.valid_from == date.today()


def test_parse_valid_from_future_date() -> None:
    """Una fila con fecha futura se parsea sin error (crea rango futuro al apply)."""
    bio = io.BytesIO(_make_xlsx([_row(valid_from="2099-01-01")]))
    res = parse_costs_xlsx_stream(bio)
    r = res.rows[0]
    assert r.ok
    assert r.valid_from == date(2099, 1, 1)


def test_parse_valid_from_invalid_yields_error() -> None:
    bio = io.BytesIO(_make_xlsx([_row(valid_from="not-a-date")]))
    res = parse_costs_xlsx_stream(bio)
    r = res.rows[0]
    assert not r.ok
    assert any("valid_from" in e for e in r.errors)
