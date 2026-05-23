import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.ficha_enrichment.extractor import (
    FichaEnrichmentExtractor,
    _build_result,
    _format_tables,
)
from app.schemas.ficha_enrich import FichaExtractionResult


MINIMAL_PDF = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog>>\nendobj\nxref\n0 1\n0000000000 65535 f\ntrailer\n<</Root 1 0 R>>\nstartxref\n9\n%%EOF"

_MOCK_TOOL_INPUT = {
    "family": "válvulas de esfera",
    "type": "esfera roscada PN30",
    "material": "brass_cw617n",
    "pn": "30",
    "temp_min_c": -20,
    "temp_max_c": 120,
    "pressure_max_bar": 30.0,
    "brand": "MT Business Key",
    "connection": "bsp",
    "specs": {
        "seat_material": "ptfe",
        "seal_material": "nbr",
        "standards": ["ISO 228/1", "WRAS"],
        "no_frost": True,
    },
    "materials": [
        {"component": "body", "material": "brass_cw617n"},
        {"component": "seat", "material": "ptfe"},
        {"component": "seal", "material": "nbr"},
    ],
    "dimensions": [
        {"dn_label": '1/4"', "values": {"L": 54.0, "H": 57.0}},
        {"dn_label": '1/2"', "values": {"L": 63.0, "H": 64.0}},
    ],
    "model_gaps": ["tabla par de apriete"],
    "confidence": 0.92,
}


def _make_mock_response(
    name: str = "extract_product_fields", data: dict | None = None
) -> MagicMock:
    block = MagicMock()
    block.type = "tool_use"
    block.name = name
    block.input = data or _MOCK_TOOL_INPUT
    resp = MagicMock()
    resp.content = [block]
    return resp


@pytest.mark.asyncio
async def test_extract_disabled_returns_empty():
    extractor = FichaEnrichmentExtractor(api_key="")
    result = await extractor.extract(pdf_bytes=MINIMAL_PDF, filename="test.pdf")
    assert result.confidence == 0.0
    assert "extractor_disabled_no_api_key" in result.model_gaps


@pytest.mark.asyncio
async def test_extract_with_mock_claude(monkeypatch):
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")

    mock_client_instance = AsyncMock()
    mock_client_instance.messages.create = AsyncMock(return_value=_make_mock_response())

    with patch("anthropic.AsyncAnthropic", return_value=mock_client_instance):
        extractor = FichaEnrichmentExtractor(api_key="sk-test")
        # Patch _classify_pages_and_extract to avoid vision calls
        extractor._classify_pages_and_extract = AsyncMock(return_value=([], [], []))
        result = await extractor.extract(pdf_bytes=MINIMAL_PDF, filename="MTFT_4097.pdf")

    assert result.scalars.pn == "30"
    assert result.scalars.temp_min_c == -20
    assert result.scalars.material == "brass_cw617n"
    assert result.specs.seat_material == "ptfe"
    assert len(result.materials) == 3
    assert result.materials[0].component == "body"
    assert len(result.dimensions) == 2
    assert result.model_gaps == ["tabla par de apriete"]
    assert result.confidence == 0.92


def test_build_result_empty_data():
    r = _build_result({}, raw_text="")
    assert isinstance(r, FichaExtractionResult)
    assert r.confidence == 0.0
    assert r.materials == []


def test_format_tables_empty():
    s = _format_tables([])
    assert "sin tablas" in s


def test_format_tables_with_data():
    tables = [{"page": 1, "headers": ["DN", "L", "H"], "rows": [['1/2"', "63", "64"]]}]
    s = _format_tables(tables)
    assert "DN" in s
    assert "63" in s


@pytest.mark.asyncio
async def test_page_classification_with_mock(monkeypatch):
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(
        return_value=_make_mock_response(
            "classify_pdf_page",
            {"kind": "dimension_drawing", "confidence": 0.9, "description": "test"},
        )
    )
    extractor = FichaEnrichmentExtractor(api_key="sk-test")
    fake_png = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100

    with patch(
        "app.services.importer_datasheets.vision_extractor._render_pdf_pages",
        return_value=[fake_png],
    ):
        clfs, assets, pts = await extractor._classify_pages_and_extract(b"%PDF", mock_client)

    assert len(clfs) == 1
    assert clfs[0].kind == "dimension_drawing"
    assert len(assets) == 1
    assert assets[0].asset_kind == "dimension_drawing"
    assert pts == []
