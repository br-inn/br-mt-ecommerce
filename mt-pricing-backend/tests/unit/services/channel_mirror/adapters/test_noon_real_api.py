"""Tests para NoonRealApiAdapter (Sprint 4 SCAFFOLD)."""

from __future__ import annotations

import httpx
import pytest

from app.services.channel_mirror.adapters.noon_real_api import (
    NoonRealApiAdapter,
    parse_noon_listing,
)

pytestmark = pytest.mark.unit


# ------------------------------ parser --------------------------------- #


def test_parser_extracts_listing_fields() -> None:
    payload = {
        "item": {
            "noon_sku": "NPSKU123",
            "title_en": "Ball Valve",
            "title_ar": "صمام كروي",
            "brand": "Pegler",
            "price": 150,
            "stock": 10,
        }
    }
    parsed = parse_noon_listing(payload)
    assert parsed["noon_id"] == "NPSKU123"
    assert parsed["title_en"] == "Ball Valve"
    assert parsed["title_ar"] == "صمام كروي"
    assert parsed["price_aed"] == 150
    assert parsed["stock_qty"] == 10


def test_parser_handles_flat_payload() -> None:
    payload = {"psku": "NP456", "title": "X", "price": 100}
    parsed = parse_noon_listing(payload)
    assert parsed["noon_id"] == "NP456"
    assert parsed["title_en"] == "X"


# ------------------------------ adapter -------------------------------- #


async def test_pull_listing_stub_fallback_when_live_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    adapter = NoonRealApiAdapter()
    listing = await adapter.pull_listing("MTV-1004")
    assert listing.raw.get("stub") is True


async def test_pull_listing_stub_fallback_without_api_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.delenv("NOON_PARTNER_API_KEY", raising=False)
    adapter = NoonRealApiAdapter()
    listing = await adapter.pull_listing("MTV-1004")
    assert listing.raw.get("stub") is True


async def test_pull_listing_calls_noon_api_with_bearer_token(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.setenv("NOON_PARTNER_API_KEY", "noonkey")

    captured: dict[str, str] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("Authorization", "")
        captured["url"] = str(request.url)
        return httpx.Response(
            200,
            json={
                "item": {
                    "noon_sku": "NPSKU",
                    "title_en": "Live title",
                    "price": 200,
                    "stock": 5,
                }
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    adapter = NoonRealApiAdapter(http_client=client)
    listing = await adapter.pull_listing("MTV-1004", external_id="N0ON-MTV1004")
    await client.aclose()
    assert listing.fields["title_en"] == "Live title"
    assert captured["auth"].startswith("Bearer noonkey")


async def test_push_diff_stub_when_live_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    adapter = NoonRealApiAdapter()
    result = await adapter.push_diff("SKU", "ID", {"title": "x"})
    assert result.ok is True
    assert result.raw.get("stub") is True


async def test_push_diff_returns_error_on_http_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.setenv("NOON_PARTNER_API_KEY", "k")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    adapter = NoonRealApiAdapter(http_client=client)
    result = await adapter.push_diff("SKU", "NPSKU", {"title": "x"})
    await client.aclose()
    assert result.ok is False
    assert "noon_error" in (result.message or "")
