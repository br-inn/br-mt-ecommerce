"""Tests para mapping_detector.detect_header_row y suggest_mapping."""

from __future__ import annotations

import io
import json
from unittest.mock import AsyncMock, MagicMock, patch

import openpyxl
import pytest

from app.services.importer.mapping_detector import detect_header_row, suggest_mapping


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
    xlsx = _make_xlsx(
        [
            ["SKU", "Familia", "HS Code", "Peso neto (kg)"],
            ["1010", "Valvulas", "73071910", 0.5],
        ]
    )
    idx, headers, samples = detect_header_row(xlsx)
    assert idx == 0
    assert headers[0] == "SKU"
    assert len(samples) == 1


def test_detect_header_row_with_title_rows():
    """Archivo con 2 filas de título antes de la cabecera real."""
    xlsx = _make_xlsx(
        [
            ["PIM CONSOLIDADO — 7,604 referencias · 42 columnas"] + [None] * 3,
            ["Generado: 2026-05-13 13:39 · Fuente: MERGED"] + [None] * 3,
            ["SKU", "Familia", "HS Code", "Peso neto (kg)"],
            ["1010", "Valvulas", "73071910", 0.5],
            ["3015", None, None, None],
        ]
    )
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
    idx, _headers, samples = detect_header_row(xlsx)
    assert idx == 0
    assert len(samples) <= 5


@pytest.mark.asyncio
async def test_suggest_mapping_parses_llm_response():
    """suggest_mapping parsea la respuesta JSON del LLM correctamente."""
    fake_json = json.dumps(
        [
            {
                "excel_col": "SKU",
                "target_field": "sku",
                "transform": "text",
                "confidence": 0.99,
                "notes": "Código de referencia",
            },
            {
                "excel_col": "Familia",
                "target_field": "family",
                "transform": "text",
                "confidence": 0.95,
                "notes": "Familia del producto",
            },
            {
                "excel_col": "Peso neto (kg)",
                "target_field": "weight",
                "transform": "decimal",
                "confidence": 0.92,
                "notes": "Peso neto",
            },
        ]
    )
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=fake_json)]

    with patch("anthropic.AsyncAnthropic") as MockAnthropicCls:
        mock_client = MockAnthropicCls.return_value
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        result = await suggest_mapping(
            headers=["SKU", "Familia", "Peso neto (kg)"],
            sample_rows=[["1010", "Valvulas", 0.5]],
            api_key="test-key",
        )

    assert len(result) == 3
    assert result[0].excel_col == "SKU"
    assert result[0].target_field == "sku"
    assert result[0].transform == "text"
    assert result[0].confidence == 0.99


@pytest.mark.asyncio
async def test_suggest_mapping_falls_back_on_invalid_json():
    """Si el LLM devuelve JSON inválido, retorna _skip fallback por cada columna."""
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text="esto no es json")]

    with patch("anthropic.AsyncAnthropic") as MockAnthropicCls:
        mock_client = MockAnthropicCls.return_value
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        result = await suggest_mapping(
            headers=["SKU", "Familia"],
            sample_rows=[["1010", "Valvulas"]],
            api_key="test-key",
        )

    # Fallback returns one _skip entry per header (confidence 0) so the UI
    # always has a mapping list to display and can request manual review.
    assert len(result) == 2
    assert all(r.target_field == "_skip" for r in result)
    assert all(r.confidence == 0.0 for r in result)
    assert result[0].excel_col == "SKU"
    assert result[1].excel_col == "Familia"


@pytest.mark.asyncio
async def test_suggest_mapping_strips_markdown_fence():
    """suggest_mapping extrae JSON de respuestas con code fence markdown."""
    fake_json = json.dumps(
        [
            {
                "excel_col": "SKU",
                "target_field": "sku",
                "transform": "text",
                "confidence": 0.99,
                "notes": "Código de referencia",
            }
        ]
    )
    fenced = f"```json\n{fake_json}\n```"
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=fenced)]

    with patch("anthropic.AsyncAnthropic") as MockAnthropicCls:
        mock_client = MockAnthropicCls.return_value
        mock_client.messages.create = AsyncMock(return_value=mock_message)
        result = await suggest_mapping(
            headers=["SKU"],
            sample_rows=[["1010"]],
            api_key="test-key",
        )

    assert len(result) == 1
    assert result[0].excel_col == "SKU"


@pytest.mark.asyncio
async def test_suggest_mapping_returns_skip_when_no_api_key():
    """Sin api_key configurada retorna fallback _skip sin llamar al LLM."""
    result = await suggest_mapping(
        headers=["SKU", "Familia"],
        sample_rows=[["1010", "Valvulas"]],
        api_key="",
    )
    assert len(result) == 2
    assert all(r.target_field == "_skip" for r in result)
    assert all(r.confidence == 0.0 for r in result)
