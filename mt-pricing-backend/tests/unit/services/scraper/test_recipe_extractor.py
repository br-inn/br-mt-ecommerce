"""Unit tests for recipe_extractor and recipe_transforms — pure logic, no IO."""
from __future__ import annotations

import pytest

from app.services.scraper.recipe_extractor import coerce_type, extract_records, field_results
from app.services.scraper.recipe_transforms import apply_transform

_SERP_HTML = """
<html><body>
  <div class="product">
    <h2 class="title">Widget A</h2>
    <span class="price">AED 49.99</span>
    <a class="link" href="/products/123">View</a>
    <span class="brand">BrandX</span>
    <img class="thumb" src="https://cdn.example.com/img/a.jpg">
    <span class="stock">In Stock</span>
    <span class="rating">4.5</span>
  </div>
  <div class="product">
    <h2 class="title">Widget B</h2>
    <span class="price">AED 99.00</span>
    <a class="link" href="/products/456">View</a>
    <span class="brand">BrandY</span>
    <img class="thumb" src="https://cdn.example.com/img/b.jpg">
    <span class="stock">Out of Stock</span>
    <span class="rating">3.8</span>
  </div>
</body></html>
"""

_RECIPE = {
    "url_templates": {"search": "http://example.com/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "title", "selector": "h2.title", "extract": "text", "type": "str"},
        {"name": "price_aed", "selector": "span.price", "extract": "text", "type": "currency"},
        {
            "name": "external_id",
            "selector": "a.link",
            "extract": "attr:href",
            "type": "str",
            "transform": {"op": "regex_capture", "pattern": r"/products/(\d+)"},
        },
        {"name": "brand", "selector": "span.brand", "extract": "text", "type": "str"},
        {"name": "image_url", "selector": "img.thumb", "extract": "attr:src", "type": "str"},
        {"name": "availability", "selector": "span.stock", "extract": "text", "type": "str"},
        {"name": "rating", "selector": "span.rating", "extract": "text", "type": "float"},
    ],
}


def test_extract_records_count():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert len(records) == 2


def test_extract_records_text_field():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["title"] == "Widget A"
    assert records[1]["title"] == "Widget B"


def test_extract_records_currency():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["price_aed"] == 49.99
    assert records[1]["price_aed"] == 99.0


def test_extract_records_attr_with_transform():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["external_id"] == "123"
    assert records[1]["external_id"] == "456"


def test_extract_records_attr_src():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["image_url"] == "https://cdn.example.com/img/a.jpg"


def test_extract_records_float():
    records = extract_records(_SERP_HTML, _RECIPE)
    assert records[0]["rating"] == 4.5
    assert records[1]["rating"] == 3.8


def test_extract_missing_selector_returns_none():
    recipe = {
        "list_item_selector": "div.product",
        "fields": [{"name": "missing", "selector": "span.nope", "extract": "text", "type": "str"}],
    }
    records = extract_records(_SERP_HTML, recipe)
    assert all(r["missing"] is None for r in records)


def test_field_results_pass():
    records = extract_records(_SERP_HTML, _RECIPE)
    results = field_results(records, _RECIPE)
    assert results["title"] == "pass"
    assert results["price_aed"] == "pass"
    assert results["external_id"] == "pass"


def test_field_results_fail_missing_selector():
    recipe = {
        "list_item_selector": "div.product",
        "fields": [{"name": "ghost", "selector": "span.ghost", "extract": "text", "type": "str"}],
    }
    records = extract_records(_SERP_HTML, recipe)
    assert field_results(records, recipe)["ghost"] == "fail"


def test_coerce_type_currency_with_symbol():
    assert coerce_type("AED 49.99", "currency") == 49.99


def test_coerce_type_currency_with_comma():
    assert coerce_type("1,250.00", "currency") == 1250.0


def test_coerce_type_currency_empty():
    assert coerce_type("", "currency") is None


def test_coerce_type_float():
    assert coerce_type("4.5", "float") == 4.5


def test_coerce_type_float_invalid():
    assert coerce_type("abc", "float") is None


def test_coerce_type_int():
    assert coerce_type("42", "int") == 42


def test_coerce_type_int_from_float_string():
    assert coerce_type("3.7", "int") == 3


def test_coerce_type_bool_truthy():
    assert coerce_type("In Stock", "bool") is True


def test_coerce_type_bool_falsy():
    assert coerce_type("Out of Stock", "bool") is False


def test_apply_transform_regex_capture():
    result = apply_transform({"op": "regex_capture", "pattern": r"/products/(\d+)"}, "/products/123")
    assert result == "123"


def test_apply_transform_regex_no_match_returns_empty():
    result = apply_transform(
        {"op": "regex_capture", "pattern": r"NOMATCH(\d+)"}, "/products/123"
    )
    assert result == ""


def test_apply_transform_strip_currency():
    result = apply_transform({"op": "strip_currency"}, "AED 49.99")
    assert result == "49.99"


def test_apply_transform_replace():
    result = apply_transform({"op": "replace", "find": "AED ", "replace_with": ""}, "AED 49.99")
    assert result == "49.99"


def test_apply_transform_map_values():
    transform = {"op": "map_values", "mapping": {"In Stock": "available", "Out": "unavailable"}}
    assert apply_transform(transform, "In Stock") == "available"
    assert apply_transform(transform, "Unknown") == "Unknown"


def test_apply_transform_unit_factor():
    result = apply_transform({"op": "unit_factor", "factor": 0.0689476}, "100")
    assert abs(float(result) - 6.89476) < 0.0001


def test_apply_transform_none_is_identity():
    assert apply_transform(None, "hello") == "hello"
