import pytest

from app.db.models.scraper_sources import ScraperSource


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
