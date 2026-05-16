"""Tests para scrape_brand_task — mock del fetcher."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.matching.ports import Query


def _make_brand(
    *,
    name: str = "Nibco",
    amazon_search_term: str | None = None,
    amazon_dept: str = "industrial",
    amazon_category_node: str | None = None,
) -> object:
    import types

    brand = types.SimpleNamespace(
        id=uuid4(),
        name=name,
        amazon_search_term=amazon_search_term,
        amazon_dept=amazon_dept,
        amazon_category_node=amazon_category_node,
        is_active=True,
    )
    return brand


def test_build_brand_query_uses_name_when_no_search_term():
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(name="Nibco")
    q = _build_brand_query(brand)

    assert isinstance(q, Query)
    assert q.text == "Nibco"
    assert q.type == "brand"
    assert q.source == "amazon_uae"
    assert q.dept == "industrial"
    assert q.category_node is None


def test_build_brand_query_prefers_amazon_search_term():
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(name="Nibco Inc.", amazon_search_term="Nibco")
    q = _build_brand_query(brand)

    assert q.text == "Nibco"


def test_build_brand_query_passes_category_node():
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(
        name="Kitz",
        amazon_dept="industrial",
        amazon_category_node="16118159031",
    )
    q = _build_brand_query(brand)

    assert q.dept == "industrial"
    assert q.category_node == "16118159031"


def test_build_brand_query_custom_dept():
    from app.workers.tasks.scraper import _build_brand_query

    brand = _make_brand(name="Crane", amazon_dept="tools")
    q = _build_brand_query(brand)

    assert q.dept == "tools"
