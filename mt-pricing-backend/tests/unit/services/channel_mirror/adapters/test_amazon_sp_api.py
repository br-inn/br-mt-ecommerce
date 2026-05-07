"""Tests para AmazonSPApiAdapter (Sprint 4 SCAFFOLD)."""

from __future__ import annotations

import httpx
import pytest

from app.services.channel_mirror.adapters.amazon_sp_api import (
    AmazonSPApiAdapter,
    parse_catalog_item,
)

pytestmark = pytest.mark.unit


# ------------------------------ parser --------------------------------- #


def test_parse_catalog_item_extracts_attributes() -> None:
    payload = {
        "asin": "B07XYZ",
        "attributes": {
            "item_name": [{"value": "Brass Ball Valve"}],
            "brand": [{"value": "Pegler"}],
            "material": [{"value": "Brass"}],
            "hs_code": [{"value": "8481.80.81"}],
        },
    }
    parsed = parse_catalog_item(payload)
    assert parsed["asin"] == "B07XYZ"
    assert parsed["title_en"] == "Brass Ball Valve"
    assert parsed["brand"] == "Pegler"
    assert parsed["material"] == "Brass"
    assert parsed["HS_code"] == "8481.80.81"


def test_parse_catalog_item_falls_back_to_summaries_for_title() -> None:
    payload = {
        "asin": "B0SUM",
        "attributes": {},
        "summaries": [{"itemName": "From summary"}],
    }
    assert parse_catalog_item(payload)["title_en"] == "From summary"


def test_parse_catalog_item_handles_empty_payload() -> None:
    parsed = parse_catalog_item({})
    assert parsed["asin"] == ""
    assert parsed["title_en"] == ""
    assert parsed["brand"] is None


# ------------------------------ adapter -------------------------------- #


async def test_pull_listing_falls_back_to_stub_when_live_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    adapter = AmazonSPApiAdapter()
    listing = await adapter.pull_listing("MTV-1004", external_id="B0CXR4M7Z9")
    # stub returns canned title
    assert listing.fields.get("title_en") == "Ball Valve PN16 DN25 Brass — MT"


async def test_pull_listing_falls_back_when_credentials_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.delenv("SP_API_REFRESH_TOKEN", raising=False)
    monkeypatch.delenv("SP_API_LWA_CLIENT_ID", raising=False)
    monkeypatch.delenv("SP_API_LWA_CLIENT_SECRET", raising=False)
    adapter = AmazonSPApiAdapter()
    listing = await adapter.pull_listing("MTV-1004", external_id="B0CXR4M7Z9")
    assert listing.raw.get("stub") is True


async def test_pull_listing_calls_sp_api_with_token_when_credentials_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.setenv("SP_API_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("SP_API_LWA_CLIENT_ID", "cid")
    monkeypatch.setenv("SP_API_LWA_CLIENT_SECRET", "secret")

    seen: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen.append(str(request.url))
        if "auth/o2/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "abc", "expires_in": 3600})
        if "/catalog/2022-04-01/items/" in str(request.url):
            return httpx.Response(
                200,
                json={
                    "asin": "B07XYZ",
                    "attributes": {"item_name": [{"value": "Live title"}]},
                },
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    adapter = AmazonSPApiAdapter(http_client=client)
    listing = await adapter.pull_listing("MTV-1004", external_id="B07XYZ")
    await client.aclose()
    assert listing.fields["title_en"] == "Live title"
    assert any("auth/o2/token" in u for u in seen)
    assert any("/catalog/2022-04-01/items/" in u for u in seen)


async def test_pull_listing_falls_back_on_http_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.setenv("SP_API_REFRESH_TOKEN", "rt")
    monkeypatch.setenv("SP_API_LWA_CLIENT_ID", "cid")
    monkeypatch.setenv("SP_API_LWA_CLIENT_SECRET", "secret")

    async def handler(request: httpx.Request) -> httpx.Response:
        if "auth/o2/token" in str(request.url):
            return httpx.Response(200, json={"access_token": "abc"})
        return httpx.Response(503)

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    adapter = AmazonSPApiAdapter(http_client=client)
    listing = await adapter.pull_listing("MTV-1004", external_id="B07XYZ")
    await client.aclose()
    # fell back to stub canned listing for MTV-1004
    assert listing.raw.get("stub") is True


async def test_push_diff_falls_back_to_stub_when_live_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    adapter = AmazonSPApiAdapter()
    result = await adapter.push_diff("SKU1", "ASIN1", {"title_en": "x"})
    assert result.ok is True
    assert "stub" in (result.message or "")
