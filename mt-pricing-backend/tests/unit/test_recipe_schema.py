import pytest
from pydantic import ValidationError

from app.schemas.scraper_sources import Recipe


def test_valid_recipe_parses():
    recipe = Recipe.model_validate(
        {
            "url_templates": {"search": "https://acme.example/s?q={query}"},
            "list_item_selector": "div.product",
            "fields": [
                {"name": "external_id", "selector": "a.pid", "extract": "attr:data-id"},
                {"name": "title", "selector": "h2.name", "extract": "text"},
                {"name": "price_aed", "selector": "span.price", "type": "currency"},
            ],
        }
    )
    assert len(recipe.fields) == 3
    assert recipe.fields[0].extract == "attr:data-id"


def test_recipe_rejects_empty_fields():
    with pytest.raises(ValidationError):
        Recipe.model_validate(
            {
                "url_templates": {"search": "https://acme.example/s?q={query}"},
                "fields": [],
            }
        )


def test_field_rejects_invalid_extract():
    with pytest.raises(ValidationError):
        Recipe.model_validate(
            {
                "url_templates": {"search": "https://acme.example/s?q={query}"},
                "fields": [{"name": "title", "selector": "h2", "extract": "bogus"}],
            }
        )
