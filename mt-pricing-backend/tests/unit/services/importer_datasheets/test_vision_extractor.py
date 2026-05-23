"""Unit tests para `app.services.importer_datasheets.vision_extractor` (US-1A-06-04-V2).

Sin pdfplumber/Pillow/HTTP — inyectamos page_renderer + client mocks.
"""

from __future__ import annotations

import os
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.importer_datasheets.vision_extractor import (
    OpenAIVisionExtractor,
    VisionExtractor,
    VisionExtractorClient,
    _parse_vision_response,
)

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _enable_live_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """La mayoría de los tests asumen MT_LIVE_NETWORK=true para entrar al pipe."""
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    # OPENAI_API_KEY presente — permite que `_resolve_client` no devuelva None
    # (los tests propios del cliente mockean la dependencia completa).
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-fake")


# ---------------------------------------------------------------------------
# _parse_vision_response
# ---------------------------------------------------------------------------
def test_parse_vision_response_clean_json() -> None:
    txt = '{"dn": "DN50", "pn": "PN16", "material": "brass", "seal": "epdm"}'
    out = _parse_vision_response(txt)
    assert out == {"dn": "DN50", "pn": "PN16", "material": "brass", "seal": "epdm"}


def test_parse_vision_response_with_prose_around() -> None:
    txt = 'Sure, here is the JSON: {"dn": "DN65"} — that\'s it.'
    out = _parse_vision_response(txt)
    assert out == {"dn": "DN65"}


def test_parse_vision_response_invalid_json_returns_empty() -> None:
    assert _parse_vision_response("totally not JSON") == {}
    assert _parse_vision_response("") == {}
    assert _parse_vision_response("{ unclosed") == {}


def test_parse_vision_response_drops_non_string_specs() -> None:
    txt = '{"dn": "DN80", "pn": 25, "material": "ss316"}'
    out = _parse_vision_response(txt)
    # pn debe descartarse (no string)
    assert out == {"dn": "DN80", "material": "ss316"}


def test_parse_vision_response_preserves_extra_dict() -> None:
    txt = '{"dn": "DN50", "extra": {"port": "DN50/40", "weight_kg": "12"}}'
    out = _parse_vision_response(txt)
    assert out["extra"] == {"port": "DN50/40", "weight_kg": "12"}


# ---------------------------------------------------------------------------
# Live disabled gate
# ---------------------------------------------------------------------------
async def test_extract_skipped_when_live_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "false")
    extractor = VisionExtractor()
    res = await extractor.extract(pdf_bytes=b"%PDF-1.4 hi", filename="x.pdf")
    assert res.skipped is True
    assert res.skip_reason == "vision_disabled_live_network_off"


async def test_extract_skipped_when_provider_not_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setenv("VLM_JUDGE_PROVIDER", "openai")
    extractor = VisionExtractor()
    res = await extractor.extract(pdf_bytes=b"%PDF-1.4", filename="x.pdf")
    assert res.skipped is True
    assert res.skip_reason == "vision_provider_not_configured"


# ---------------------------------------------------------------------------
# Happy path with mocked client + renderer
# ---------------------------------------------------------------------------
class _MockClient:
    def __init__(self, responses: list[str]) -> None:
        self._responses = list(responses)
        self.calls: list[dict[str, Any]] = []

    async def extract(self, *, png_bytes: bytes, prompt: str) -> str:
        self.calls.append({"png_len": len(png_bytes), "prompt": prompt})
        if not self._responses:
            return "{}"
        return self._responses.pop(0)


def _renderer_factory(num_pages: int = 1) -> Any:
    def _render(pdf_bytes: bytes, *, max_pages: int = 4, **_kw: Any) -> list[bytes]:
        n = min(num_pages, max_pages)
        return [b"\x89PNG\r\nfake-page-%d" % i for i in range(n)]

    return _render


async def test_extract_happy_single_page() -> None:
    client = _MockClient(['{"dn":"DN50","pn":"PN16","material":"brass","seal":"epdm"}'])
    extractor = VisionExtractor(client=client, page_renderer=_renderer_factory(1))
    res = await extractor.extract(pdf_bytes=b"%PDF-1.4", filename="MTFT_5114.pdf")
    assert res.skipped is False
    assert res.error is None
    assert len(res.pages) == 1
    assert res.specs["dn"] == "DN50"
    assert res.specs["pn"] == "PN16"
    assert res.specs["material"] == "brass"
    assert res.specs["seal"] == "epdm"
    # Confidence con 4 specs / 4 = 1.0
    assert res.confidence == pytest.approx(1.0)
    assert len(client.calls) == 1


async def test_extract_multi_page_first_wins() -> None:
    client = _MockClient(
        [
            '{"dn":"DN50","material":"brass"}',  # page 0
            '{"dn":"DN999","pn":"PN16","seal":"epdm"}',  # page 1: extras + ignores DN
        ]
    )
    extractor = VisionExtractor(client=client, page_renderer=_renderer_factory(2))
    res = await extractor.extract(pdf_bytes=b"%PDF-1.4", filename="x.pdf")
    assert res.specs["dn"] == "DN50"  # first page wins
    assert res.specs["material"] == "brass"
    assert res.specs["pn"] == "PN16"
    assert res.specs["seal"] == "epdm"


async def test_extract_handles_renderer_failure() -> None:
    def _broken_renderer(_pdf: bytes, **_kw: Any) -> list[bytes]:
        raise RuntimeError("pdfplumber crashed")

    extractor = VisionExtractor(client=_MockClient([]), page_renderer=_broken_renderer)
    res = await extractor.extract(pdf_bytes=b"%PDF-1.4", filename="x.pdf")
    assert res.error is not None
    assert "pdf_render_failed" in res.error


async def test_extract_handles_empty_renderer() -> None:
    def _empty(_pdf: bytes, **_kw: Any) -> list[bytes]:
        return []

    extractor = VisionExtractor(client=_MockClient([]), page_renderer=_empty)
    res = await extractor.extract(pdf_bytes=b"%PDF-1.4", filename="x.pdf")
    assert res.error == "pdf_render_empty"


async def test_extract_continues_when_client_raises() -> None:
    class _FlakyClient:
        async def extract(self, *, png_bytes: bytes, prompt: str) -> str:
            raise RuntimeError("openai 500")

    extractor = VisionExtractor(client=_FlakyClient(), page_renderer=_renderer_factory(2))
    res = await extractor.extract(pdf_bytes=b"%PDF-1.4", filename="x.pdf")
    # Sin specs detectados → confidence 0
    assert res.specs == {}
    assert res.confidence == 0.0
    assert len(res.pages) == 2  # two pages still iterated


# ---------------------------------------------------------------------------
# OpenAIVisionExtractor: HTTP shape (no red real)
# ---------------------------------------------------------------------------
async def test_openai_vision_extractor_uses_data_url() -> None:
    """Verifica que envía base64 data-URL + auth header — sin red."""
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json = MagicMock(
        return_value={"choices": [{"message": {"content": '{"dn":"DN100"}'}}]}
    )
    fake_http = MagicMock()
    fake_http.post = AsyncMock(return_value=fake_response)

    extractor = OpenAIVisionExtractor(api_key="sk-test", model="gpt-4o-mini", http_client=fake_http)
    out = await extractor.extract(png_bytes=b"\x89PNGdata", prompt="hello")
    assert out == '{"dn":"DN100"}'
    fake_http.post.assert_awaited_once()
    args, kwargs = fake_http.post.await_args
    body = kwargs["json"]
    headers = kwargs["headers"]
    assert headers["Authorization"] == "Bearer sk-test"
    # message[0].content[1].image_url.url comienza con data:image/png;base64,
    img_url = body["messages"][0]["content"][1]["image_url"]["url"]
    assert img_url.startswith("data:image/png;base64,")
