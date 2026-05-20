from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models.scraper_sources import ScraperSourceTestRun
from app.repositories.scraper_sources import ScraperSourceRepository
from app.services.scraper.source_validation_service import SourceValidationService

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraper_sources" / "serp_sample.html"

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "external_id", "selector": "h2.name", "extract": "text"},
        {"name": "title", "selector": "h2.name", "extract": "text"},
        {"name": "missing", "selector": "span.nope", "extract": "text"},
    ],
}


@pytest.mark.integration
async def test_validate_records_and_persists_test_run(db_session):
    repo = ScraperSourceRepository(db_session)
    source = await repo.create(
        name="ACME", slug="acme-val", base_url="https://acme.example",
        destination_profile="competitor_price",
    )
    recipe_row = await repo.add_recipe(source.id, _RECIPE)

    html = _FIXTURE.read_text(encoding="utf-8")

    async def fake_fetch(url: str) -> str:
        return html

    service = SourceValidationService(db_session)
    result = await service.validate(
        source.id, recipe_row.id, "https://acme.example/s?q=valvula",
        html_fetcher=fake_fetch,
    )

    assert len(result["records"]) == 2
    assert result["field_results"]["title"] == "pass"
    assert result["field_results"]["missing"] == "fail"
    assert result["status"] == "failing"

    refreshed = await repo.get_recipe(recipe_row.id)
    assert refreshed.validation_status == "failing"

    runs = (
        await db_session.execute(
            select(ScraperSourceTestRun).where(ScraperSourceTestRun.source_id == source.id)
        )
    ).scalars().all()
    assert len(runs) == 1
