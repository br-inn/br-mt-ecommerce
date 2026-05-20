import pytest

from app.repositories.scraper_sources import ScraperSourceRepository
from app.services.matching.adapter_registry import resolve_fetcher
from app.services.matching.adapters.generic_configurable import GenericConfigurableFetcher

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [{"name": "title", "selector": "h2.name"}],
}


@pytest.mark.integration
async def test_resolve_hardcoded_channel_returns_existing(db_session):
    fetcher = await resolve_fetcher("amazon_uae", db_session)
    assert fetcher.channel == "amazon_uae"


@pytest.mark.integration
async def test_resolve_source_slug_returns_generic(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await repo.create(
        name="ACME", slug="acme-resolve", base_url="https://acme.example",
        destination_profile="competitor_price",
    )
    recipe_row = await repo.add_recipe(source.id, _RECIPE)
    await repo.set_recipe_live(recipe_row.id)
    source.status = "active"
    await db_session.flush()

    fetcher = await resolve_fetcher("acme-resolve", db_session)
    assert isinstance(fetcher, GenericConfigurableFetcher)
    assert fetcher.channel == "acme-resolve"


@pytest.mark.integration
async def test_resolve_unknown_channel_raises(db_session):
    with pytest.raises(ValueError, match="Unknown matching channel"):
        await resolve_fetcher("does-not-exist", db_session)
