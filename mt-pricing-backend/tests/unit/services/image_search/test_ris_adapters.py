"""Tests unitarios para RIS adapters — US-F15-02-03."""

from __future__ import annotations

from decimal import Decimal
from unittest.mock import AsyncMock

import httpx
import pytest
import respx

from app.services.comparator.interfaces import ReverseImageHit, ReverseImageSearchResult
from app.services.image_search.ris_adapters import (
    NoopRisAdapter,
    RateLimitedRisAdapter,
    TinEyeAdapter,
)
from app.services.image_search.ris_boost import apply_ris_boost


# ---------------------------------------------------------------------------
# T9.1 — test_noop_returns_empty_hits
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_noop_returns_empty_hits() -> None:
    adapter = NoopRisAdapter()
    result = await adapter.search(image_url="https://example.com/img.jpg")
    assert result.provider == "noop"
    assert result.hits == ()


# ---------------------------------------------------------------------------
# T9.1 — test_daily_limit_reached_returns_empty
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_daily_limit_reached_returns_empty() -> None:
    fake_redis = AsyncMock()
    fake_redis.incr.return_value = 201  # ya superó el límite de 200

    inner = NoopRisAdapter()
    rate_limited = RateLimitedRisAdapter(inner, redis=fake_redis, limit=200)

    result = await rate_limited.search(image_url="https://example.com/img.jpg")
    assert result.provider == "limit_reached"
    assert result.hits == ()


# ---------------------------------------------------------------------------
# T9.1 — test_tineye_adapter_maps_response
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tineye_adapter_maps_response() -> None:
    mock_response = {
        "results": {
            "matches": [
                {
                    "image_url": "https://example.com/img.jpg",
                    "domain": "example.com",
                    "score": 0.85,
                }
            ]
        }
    }
    with respx.mock:
        respx.get("https://api.tineye.com/rest/search/").mock(
            return_value=httpx.Response(200, json=mock_response)
        )
        adapter = TinEyeAdapter(api_key="test-key")
        result = await adapter.search(image_url="https://foo.com/product.jpg")

    assert result.provider == "tineye"
    assert len(result.hits) == 1
    assert result.hits[0].domain == "example.com"
    assert result.hits[0].similarity == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# T9.1 — test_apply_ris_boost_canonical_match
# ---------------------------------------------------------------------------


def test_apply_ris_boost_canonical_match() -> None:
    hit = ReverseImageHit(
        url="https://manufacturer.com/product.jpg",
        domain="manufacturer.com",
        similarity=0.9,
    )
    result = ReverseImageSearchResult(
        provider="tineye",
        hits=(hit,),
        searched_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    canonical_domains = frozenset({"manufacturer.com"})
    confidence = Decimal("0.40")

    boosted, was_boosted = apply_ris_boost(confidence, result, canonical_domains)

    assert was_boosted is True
    assert boosted == Decimal("0.55")


def test_apply_ris_boost_no_match_returns_original() -> None:
    hit = ReverseImageHit(url="https://other.com/img.jpg", domain="other.com", similarity=0.5)
    result = ReverseImageSearchResult(
        provider="tineye",
        hits=(hit,),
        searched_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    confidence = Decimal("0.40")
    canonical_domains = frozenset({"manufacturer.com"})

    boosted, was_boosted = apply_ris_boost(confidence, result, canonical_domains)

    assert was_boosted is False
    assert boosted == confidence


def test_apply_ris_boost_caps_at_one() -> None:
    hit = ReverseImageHit(url="https://mfr.com/img.jpg", domain="mfr.com", similarity=1.0)
    result = ReverseImageSearchResult(
        provider="tineye",
        hits=(hit,),
        searched_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    confidence = Decimal("0.95")
    canonical_domains = frozenset({"mfr.com"})

    boosted, was_boosted = apply_ris_boost(confidence, result, canonical_domains)

    assert was_boosted is True
    assert boosted == Decimal("1.0")
