from pathlib import Path

import pytest

from app.repositories.scraper_sources import ScraperSourceRepository
from app.workers.tasks.scraper import _scrape_source_async

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraper_sources" / "serp_sample.html"

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "external_id", "selector": "h2.name", "extract": "text"},
        {"name": "title", "selector": "h2.name", "extract": "text"},
        {"name": "brand", "selector": "span.brand", "extract": "text"},
        {"name": "price_aed", "selector": "span.price", "type": "currency"},
    ],
}


@pytest.mark.integration
async def test_scrape_source_async_upserts_listings(db_session):
    from app.db.models.comparator import CompetitorBrand

    brand = CompetitorBrand(name="ACME", amazon_dept="industrial", is_active=True)
    db_session.add(brand)
    await db_session.flush()

    repo = ScraperSourceRepository(db_session)
    source = await repo.create(
        name="ACME", slug="acme-task", base_url="https://acme.example",
        destination_profile="competitor_price", competitor_brand_id=brand.id,
    )
    recipe_row = await repo.add_recipe(source.id, _RECIPE)
    await repo.set_recipe_live(recipe_row.id)
    source.status = "active"
    await db_session.flush()

    html = _FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(url: str) -> str:
        return html

    result = await _scrape_source_async(
        db_session, str(source.id), search_text="valvula", html_fetcher=fake_fetch
    )
    assert result["status"] == "ok"
    assert result["upserted"] == 2
