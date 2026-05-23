import pytest

from app.db.models.scraper_sources import ScraperSource
from app.repositories.scraper_sources import ScraperSourceRepository


@pytest.mark.integration
async def test_scraper_source_persists(db_session):
    source = ScraperSource(
        name="ACME Tools",
        slug="acme-tools",
        base_url="https://acme.example",
        destination_profile="competitor_price",
        fetch_mode="static",
        status="draft",
    )
    db_session.add(source)
    await db_session.flush()

    assert source.id is not None
    assert source.created_at is not None
    assert source.status == "draft"


_RECIPE_A = {"url_templates": {"search": "x"}, "fields": [{"name": "title", "selector": "h2"}]}
_RECIPE_B = {"url_templates": {"search": "y"}, "fields": [{"name": "title", "selector": "h3"}]}


async def _make_source(repo: ScraperSourceRepository, slug: str = "acme") -> "object":
    return await repo.create(
        name="ACME",
        slug=slug,
        base_url="https://acme.example",
        destination_profile="competitor_price",
    )


@pytest.mark.integration
async def test_repo_create_and_get_by_slug(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await _make_source(repo, "acme-1")
    fetched = await repo.get_by_slug("acme-1")
    assert fetched is not None
    assert fetched.id == source.id


@pytest.mark.integration
async def test_repo_add_recipe_increments_version(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await _make_source(repo, "acme-2")
    r1 = await repo.add_recipe(source.id, _RECIPE_A)
    r2 = await repo.add_recipe(source.id, _RECIPE_B)
    assert r1.version == 1
    assert r2.version == 2


@pytest.mark.integration
async def test_repo_set_recipe_live_is_exclusive(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await _make_source(repo, "acme-3")
    r1 = await repo.add_recipe(source.id, _RECIPE_A)
    r2 = await repo.add_recipe(source.id, _RECIPE_B)
    await repo.set_recipe_live(r1.id)
    await repo.set_recipe_live(r2.id)
    live = await repo.get_live_recipe(source.id)
    assert live is not None
    assert live.id == r2.id
