"""Tests for ScraperAgentService — real Claude API + local HTTP fixture server.

Requires ANTHROPIC_API_KEY env var for integration tests.
"""
from __future__ import annotations

import pytest

from app.services.scraper.agent_service import ScraperAgentService, _detect_mode
from app.services.scraper.canonical_fields import REQUIRED_FIELDS


def test_detect_mode_static_with_rich_html():
    html = "<html><body>" + "<p>Product content</p>" * 50 + "</body></html>"
    assert _detect_mode(html, "http://example.com") == "static"


def test_detect_mode_headless_empty_body():
    html = "<html><head><title>App</title></head><body><div id='root'></div></body></html>"
    assert _detect_mode(html, "http://example.com") == "headless"


def test_detect_mode_stealth_cloudflare():
    # Body must have >= 500 chars of text for the cloudflare check to trigger
    html = (
        "<html><body>"
        + "<p>Product content for testing stealth detection</p>" * 15
        + "<script>__cf_chl_rt_tk='abc'</script>"
        + "</body></html>"
    )
    assert _detect_mode(html, "http://example.com") == "stealth"


def test_detect_mode_headless_none_body():
    html = "<html></html>"
    assert _detect_mode(html, "http://example.com") == "headless"


@pytest.mark.integration
async def test_analyze_returns_required_fields(html_fixture_server: str):
    """Claude analyzes the generic_serp.html fixture and proposes canonical fields."""
    service = ScraperAgentService()
    result = await service.analyze(f"{html_fixture_server}/generic_serp.html")

    assert result.detected_mode == "static"

    recipe_field_names = {f["name"] for f in result.proposed_recipe.get("fields", [])}
    # Claude must propose at least title and price_aed from the fixture HTML
    assert "title" in recipe_field_names, f"title missing from {recipe_field_names}"
    assert "price_aed" in recipe_field_names, f"price_aed missing from {recipe_field_names}"

    # preview_records should reflect the 3 product cards in the fixture
    assert len(result.preview_records) == 3
    assert result.preview_records[0].get("title") is not None

    # proposed_source should have name, slug, base_url
    assert result.proposed_source["base_url"].startswith("http://127.0.0.1")


@pytest.mark.integration
async def test_analyze_detects_headless_for_js_page(html_fixture_server: str):
    """js_heavy.html fixture has empty body — should be detected as headless."""
    service = ScraperAgentService()
    result = await service.analyze(f"{html_fixture_server}/js_heavy.html")
    assert result.detected_mode == "headless"
    assert any("headless" in w for w in result.warnings)


@pytest.mark.integration
async def test_analyze_hint_returns_single_field(html_fixture_server: str):
    """When hint is set, Claude returns exactly one field."""
    service = ScraperAgentService()
    result = await service.analyze(
        f"{html_fixture_server}/generic_serp.html",
        hint="the product delivery time text",
    )
    fields = result.proposed_recipe.get("fields", [])
    assert len(fields) == 1
    assert fields[0].get("selector") is not None
