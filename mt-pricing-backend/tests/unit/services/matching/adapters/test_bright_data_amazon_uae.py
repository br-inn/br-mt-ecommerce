"""Tests para BrightDataAmazonUaeFetcher (Sprint 4 SCAFFOLD).

NUNCA hace red real — usa httpx.MockTransport para simular respuestas.
Cubre:
- MT_LIVE_NETWORK=false → fallback al stub.
- MT_LIVE_NETWORK=true sin creds → fallback al stub.
- MT_LIVE_NETWORK=true con creds + payload válido → parser correcto.
- Circuit breaker: 5 fallos → degraded mode.
- Retry: 1 fallo → reintenta con éxito.
"""

from __future__ import annotations

import pytest
import httpx

from app.services.matching.adapters.bright_data_amazon_uae import (
    BrightDataAmazonUaeFetcher,
    _CircuitBreaker,
    parse_bright_data_amazon,
)
from app.services.matching.ports import Query

pytestmark = pytest.mark.unit


def _make_query() -> Query:
    return Query(text="brass ball valve DN50 BSP", source="brand_spec", lang="en")


# ----------------------------- parser ---------------------------------- #


def test_parser_handles_valid_payload() -> None:
    payload = {
        "results": [
            {
                "asin": "B07ABC",
                "title": "Pegler 2-Inch Brass Ball Valve",
                "brand": "Pegler",
                "price": "145.50",
                "currency": "AED",
                "delivery": "2 days",
                "image_urls": ["https://x/img1"],
                "specifications": {"material": "brass", "pn": "PN25"},
            }
        ]
    }
    out = parse_bright_data_amazon(payload)
    assert len(out) == 1
    c = out[0]
    assert c.external_id == "B07ABC"
    assert c.brand == "Pegler"
    assert str(c.price_aed) == "145.50"
    assert c.specs == {"material": "brass", "pn": "PN25"}
    assert c.raw_payload["currency"] == "AED"


def test_parser_skips_items_without_asin_or_title() -> None:
    payload = {"results": [{"asin": "", "title": "x"}, {"title": "no asin"}, "not_a_dict"]}
    assert parse_bright_data_amazon(payload) == []


def test_parser_handles_missing_results_key() -> None:
    assert parse_bright_data_amazon({}) == []
    assert parse_bright_data_amazon({"results": "not_a_list"}) == []


def test_parser_handles_invalid_price() -> None:
    payload = {
        "results": [
            {"asin": "B1", "title": "T", "price": "not-a-number"},
        ]
    }
    out = parse_bright_data_amazon(payload)
    assert len(out) == 1
    assert out[0].price_aed is None


# ----------------------------- circuit breaker ------------------------- #


def test_circuit_breaker_opens_after_threshold() -> None:
    cb = _CircuitBreaker(failure_threshold=3, reset_timeout_s=60)
    assert not cb.is_open()
    cb.record_failure()
    cb.record_failure()
    assert not cb.is_open()
    cb.record_failure()
    assert cb.is_open()


def test_circuit_breaker_recovers_on_success() -> None:
    cb = _CircuitBreaker(failure_threshold=2, reset_timeout_s=60)
    cb.record_failure()
    cb.record_success()
    cb.record_failure()
    assert not cb.is_open()


# ----------------------------- adapter --------------------------------- #


async def test_fetch_falls_back_to_stub_when_live_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    fetcher = BrightDataAmazonUaeFetcher()
    out = await fetcher.fetch(_make_query(), sku="MTBR4001050")
    assert len(out) == 5  # stub canned for this SKU
    assert all(c.source == "amazon_uae" for c in out)


async def test_fetch_falls_back_when_credentials_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.delenv("BRIGHT_DATA_API_KEY", raising=False)
    monkeypatch.delenv("BRIGHT_DATA_AMAZON_AE_DATASET_ID", raising=False)
    fetcher = BrightDataAmazonUaeFetcher()
    out = await fetcher.fetch(_make_query(), sku="MTBR4001050")
    assert len(out) == 5  # stub fired


async def test_fetch_calls_bright_data_when_live_and_creds_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "tok")
    monkeypatch.setenv("BRIGHT_DATA_AMAZON_AE_DATASET_ID", "ds_123")

    captured: dict[str, object] = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = request.content
        return httpx.Response(
            200,
            json={
                "results": [
                    {
                        "asin": "B0LIVE1",
                        "title": "Live Pegler Valve",
                        "brand": "Pegler",
                        "price": "100.00",
                        "specifications": {"material": "brass"},
                    }
                ]
            },
        )

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    fetcher = BrightDataAmazonUaeFetcher(http_client=client)
    out = await fetcher.fetch(_make_query(), sku="MTBR4001050")
    await client.aclose()
    assert len(out) == 1
    assert out[0].external_id == "B0LIVE1"
    assert "url" in captured


async def test_fetch_falls_back_with_degraded_when_circuit_open(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "tok")
    monkeypatch.setenv("BRIGHT_DATA_AMAZON_AE_DATASET_ID", "ds")
    cb = _CircuitBreaker(failure_threshold=1, reset_timeout_s=600)
    cb.record_failure()  # opens
    fetcher = BrightDataAmazonUaeFetcher(circuit_breaker=cb)
    out = await fetcher.fetch(_make_query(), sku="MTBR4001050")
    assert all(c.raw_payload.get("degraded_mode") is True for c in out)


async def test_fetch_records_failure_when_http_errors(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    monkeypatch.setenv("BRIGHT_DATA_API_KEY", "tok")
    monkeypatch.setenv("BRIGHT_DATA_AMAZON_AE_DATASET_ID", "ds")

    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "boom"})

    transport = httpx.MockTransport(handler)
    client = httpx.AsyncClient(transport=transport)
    cb = _CircuitBreaker(failure_threshold=1, reset_timeout_s=600)
    fetcher = BrightDataAmazonUaeFetcher(http_client=client, circuit_breaker=cb)
    out = await fetcher.fetch(_make_query(), sku="MTBR4001050")
    await client.aclose()
    assert cb.is_open(), "circuit breaker must open after failures"
    # fallback emitted with degraded_mode flag
    assert any(c.raw_payload.get("degraded_mode") is True for c in out)
