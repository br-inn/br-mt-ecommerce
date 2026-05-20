from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.matching.adapters.generic_configurable import GenericConfigurableFetcher
from app.services.matching.ports import Query

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraper_sources" / "serp_sample.html"

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "external_id", "selector": "h2.name", "extract": "text"},
        {"name": "title", "selector": "h2.name", "extract": "text"},
        {"name": "brand", "selector": "span.brand", "extract": "text"},
        {"name": "price_aed", "selector": "span.price", "type": "currency"},
        {"name": "stock", "selector": "span.stock", "extract": "text"},
    ],
}


def _source(fetch_mode="static"):
    return SimpleNamespace(slug="acme-tools", fetch_mode=fetch_mode)


async def test_fetch_maps_records_to_candidate_raw():
    html = _FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(url: str) -> str:
        assert url == "https://acme.example/s?q=valvula"
        return html

    fetcher = GenericConfigurableFetcher(_source(), _RECIPE, html_fetcher=fake_fetch)
    out = await fetcher.fetch(Query(text="valvula", source="acme-tools"))

    assert fetcher.channel == "acme-tools"
    assert len(out) == 2
    first = out[0]
    assert first.source == "acme-tools"
    assert first.title == 'Bola de acero inox 1/2"'
    assert str(first.price_aed) == "1250.0"
    assert first.brand == "ACME"
    assert first.specs["stock"] == "In Stock"


async def test_non_static_fetch_mode_raises():
    with pytest.raises(NotImplementedError, match="headless"):
        GenericConfigurableFetcher(_source(fetch_mode="headless"), _RECIPE)
