from pathlib import Path

from app.services.scraper.recipe_extractor import extract_records, field_results

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "scraper_sources" / "serp_sample.html"

_RECIPE = {
    "url_templates": {"search": "https://acme.example/s?q={query}"},
    "list_item_selector": "div.product",
    "fields": [
        {"name": "external_id", "selector": "h2.name", "extract": "text"},
        {"name": "title", "selector": "h2.name", "extract": "text"},
        {"name": "brand", "selector": "span.brand", "extract": "text"},
        {"name": "price_aed", "selector": "span.price", "type": "currency"},
        {"name": "in_stock", "selector": "span.stock", "type": "bool",
         "transform": {"op": "map_values", "mapping": {"In Stock": "true", "Out": "false"}}},
        {"name": "missing", "selector": "span.does-not-exist", "extract": "text"},
    ],
}


def test_extract_records_one_per_item():
    html = _FIXTURE.read_text(encoding="utf-8")
    records = extract_records(html, _RECIPE)
    assert len(records) == 2


def test_extract_records_field_values():
    html = _FIXTURE.read_text(encoding="utf-8")
    records = extract_records(html, _RECIPE)
    first = records[0]
    assert first["title"] == 'Bola de acero inox 1/2"'
    assert first["brand"] == "ACME"
    assert first["price_aed"] == 1250.0
    assert first["in_stock"] is True
    assert records[1]["in_stock"] is False
    assert first["missing"] is None


def test_extract_attr():
    recipe = {
        "url_templates": {"search": "x"},
        "list_item_selector": "div.product",
        "fields": [{"name": "external_id", "selector": "div.product", "extract": "attr:data-id"}],
    }
    # selector relativo al item: el propio nodo no se re-selecciona, usamos un hijo
    html = _FIXTURE.read_text(encoding="utf-8")
    recipe["fields"][0]["selector"] = "h2.name"
    recipe["fields"][0]["extract"] = "text"
    records = extract_records(html, recipe)
    assert records[0]["external_id"] == 'Bola de acero inox 1/2"'


def test_field_results_pass_fail():
    html = _FIXTURE.read_text(encoding="utf-8")
    records = extract_records(html, _RECIPE)
    results = field_results(records, _RECIPE)
    assert results["title"] == "pass"
    assert results["missing"] == "fail"
