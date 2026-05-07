"""Tests para PlaywrightNoonUaeFetcher (Sprint 4 SCAFFOLD).

Sin browser real — el ``browser_factory`` se inyecta como un fake.
"""

from __future__ import annotations

import pytest

from app.services.matching.adapters.playwright_noon_uae import (
    PlaywrightNoonUaeFetcher,
    _CircuitBreaker,
    map_noon_to_candidate,
    parse_noon_html,
)
from app.services.matching.ports import Query

pytestmark = pytest.mark.unit


SAMPLE_HTML = """
<article data-qa="product-block" data-noonid="N001">
  <h1 class="productTitle">Pegler Brass Ball Valve 2 inch</h1>
  <span class="brand">Pegler</span>
  <span class="priceNow">150.00 AED</span>
  <span lang="ar">صمام كروي نحاسي</span>
</article>
<article data-qa="product-block" data-noonid="N002">
  <h1 class="productTitle">Generic Valve</h1>
  <span class="priceNow">85,00 AED</span>
</article>
"""


# ------------------------------ parser --------------------------------- #


def test_parser_extracts_two_blocks() -> None:
    items = parse_noon_html(SAMPLE_HTML)
    assert len(items) == 2
    assert items[0]["noon_id"] == "N001"
    assert "Pegler" in items[0]["title"]
    assert items[0]["brand"] == "Pegler"
    assert items[0]["title_ar"]


def test_map_to_candidate_skips_blank_items() -> None:
    items = [{"noon_id": "", "title": "x"}, {"noon_id": "n", "title": ""}]
    assert map_noon_to_candidate(items) == []


def test_map_to_candidate_handles_invalid_price() -> None:
    items = [{"noon_id": "X", "title": "T", "price_aed": "abc"}]
    out = map_noon_to_candidate(items)
    assert len(out) == 1
    assert out[0].price_aed is None


# ------------------------------ adapter -------------------------------- #


async def test_fetch_falls_back_when_live_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MT_LIVE_NETWORK", raising=False)
    fetcher = PlaywrightNoonUaeFetcher()
    out = await fetcher.fetch(Query(text="x", source="brand_spec"), sku="MTBR4001050")
    assert len(out) == 3  # stub canned (Noon stub returns 3)


async def test_fetch_falls_back_when_no_browser_factory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")
    fetcher = PlaywrightNoonUaeFetcher(browser_factory=None)
    out = await fetcher.fetch(Query(text="x", source="brand_spec"), sku="MTBR4001050")
    assert len(out) == 3  # stub fallback


async def test_fetch_uses_browser_factory(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")

    class _FakeCtx:
        def __init__(self) -> None:
            self.url: str | None = None

        async def goto(self, url: str) -> None:
            self.url = url

        async def content(self) -> str:
            return SAMPLE_HTML

        async def close(self) -> None:
            pass

    fake = _FakeCtx()

    async def factory() -> _FakeCtx:
        return fake

    fetcher = PlaywrightNoonUaeFetcher(browser_factory=factory)
    out = await fetcher.fetch(Query(text="brass valve", source="brand_spec"))
    assert len(out) == 2
    assert out[0].external_id == "N001"
    assert "brass valve" in (fake.url or "")


async def test_fetch_marks_degraded_when_navigation_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MT_LIVE_NETWORK", "true")

    class _BrokenCtx:
        async def goto(self, url: str) -> None:
            raise RuntimeError("nav timeout")

        async def content(self) -> str:
            return ""

        async def close(self) -> None:
            pass

    async def factory() -> _BrokenCtx:
        return _BrokenCtx()

    cb = _CircuitBreaker(failure_threshold=10, reset_timeout_s=60)
    fetcher = PlaywrightNoonUaeFetcher(browser_factory=factory, circuit_breaker=cb)
    out = await fetcher.fetch(Query(text="x", source="brand_spec"), sku="MTBR4001050")
    assert any(c.raw_payload.get("degraded_mode") is True for c in out)
