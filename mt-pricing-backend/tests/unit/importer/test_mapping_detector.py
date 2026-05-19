"""Tests para mapping_detector.detect_header_row."""
from __future__ import annotations

import io
import openpyxl

from app.services.importer.mapping_detector import detect_header_row


def _make_xlsx(rows: list[list]) -> bytes:
    """Crea un xlsx en memoria con las filas dadas."""
    wb = openpyxl.Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def test_detect_header_row_no_title():
    """Archivo sin filas de título: cabecera en fila 0."""
    xlsx = _make_xlsx([
        ["SKU", "Familia", "HS Code", "Peso neto (kg)"],
        ["1010", "Valvulas", "73071910", 0.5],
    ])
    idx, headers, samples = detect_header_row(xlsx)
    assert idx == 0
    assert headers[0] == "SKU"
    assert len(samples) == 1


def test_detect_header_row_with_title_rows():
    """Archivo con 2 filas de título antes de la cabecera real."""
    xlsx = _make_xlsx([
        ["PIM CONSOLIDADO — 7,604 referencias · 42 columnas"] + [None] * 3,
        ["Generado: 2026-05-13 13:39 · Fuente: MERGED"] + [None] * 3,
        ["SKU", "Familia", "HS Code", "Peso neto (kg)"],
        ["1010", "Valvulas", "73071910", 0.5],
        ["3015", None, None, None],
    ])
    idx, headers, samples = detect_header_row(xlsx)
    assert idx == 2
    assert headers[0] == "SKU"
    assert len(samples) == 2
    assert samples[0][0] == "1010"
    assert samples[1][0] == "3015"


def test_detect_header_row_returns_up_to_5_samples():
    """Devuelve máximo 5 filas de datos como muestra."""
    rows = [["SKU", "Familia", "HS Code"]] + [[str(i), "Val", "73071910"] for i in range(10)]
    xlsx = _make_xlsx(rows)
    idx, headers, samples = detect_header_row(xlsx)
    assert idx == 0
    assert len(samples) <= 5
