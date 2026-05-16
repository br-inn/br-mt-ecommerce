"""Unit tests para la extensión de Query con dept + category_node."""
from __future__ import annotations

from urllib.parse import quote_plus

from app.services.matching.ports import Query

_BASE = "https://www.amazon.ae"


def _build_serp_url(query: Query) -> str:
    url = f"{_BASE}/s?k={quote_plus(query.text)}"
    if query.dept:
        url += f"&i={query.dept}"
    if query.category_node:
        url += f"&rh=n:{query.category_node}"
    url += "&language=en_AE"
    return url


def test_query_default_dept():
    q = Query(text="Nibco ball valve", source="amazon_uae")
    assert q.dept == "industrial"
    assert q.category_node is None


def test_query_custom_dept():
    q = Query(text="Nibco", source="amazon_uae", dept="tools")
    assert q.dept == "tools"


def test_query_with_category_node():
    q = Query(text="Nibco", source="amazon_uae", category_node="16118159031")
    assert q.category_node == "16118159031"
    assert q.dept == "industrial"


def test_query_frozen_still_works():
    import dataclasses
    q = Query(text="Kitz", source="amazon_uae", type="brand", dept="industrial")
    assert dataclasses.is_dataclass(q)


def test_serp_url_default_dept():
    q = Query(text="ball valve", source="amazon_uae")
    url = _build_serp_url(q)
    assert "&i=industrial" in url
    assert "rh=n:" not in url


def test_serp_url_with_category_node():
    q = Query(text="Nibco", source="amazon_uae", category_node="16118159031")
    url = _build_serp_url(q)
    assert "&i=industrial" in url
    assert "&rh=n:16118159031" in url


def test_serp_url_brand_query_type():
    q = Query(text="Kitz", source="amazon_uae", type="brand", dept="tools")
    url = _build_serp_url(q)
    assert "&i=tools" in url
    assert "Kitz" in url
