"""Unit tests for canonical_fields — pure logic, no IO."""
from __future__ import annotations

import json

import pytest

from app.services.scraper.canonical_fields import (
    CANONICAL_FIELDS,
    REQUIRED_FIELDS,
    fields_as_schema_json,
    validate_recipe,
)


def test_required_fields_set():
    assert REQUIRED_FIELDS == {"external_id", "title", "price_aed"}


def test_canonical_fields_count():
    assert len(CANONICAL_FIELDS) == 10


def test_validate_recipe_all_missing():
    missing = validate_recipe({"fields": []})
    assert set(missing) == {"external_id", "title", "price_aed"}


def test_validate_recipe_all_required_present():
    recipe = {
        "fields": [
            {"name": "external_id", "selector": "a", "extract": "attr:href", "type": "str"},
            {"name": "title", "selector": "h2", "extract": "text", "type": "str"},
            {"name": "price_aed", "selector": "span.price", "extract": "text", "type": "currency"},
        ]
    }
    assert validate_recipe(recipe) == []


def test_validate_recipe_partial_missing():
    recipe = {
        "fields": [
            {"name": "title", "selector": "h2", "extract": "text", "type": "str"},
            {"name": "price_aed", "selector": "span", "extract": "text", "type": "currency"},
        ]
    }
    missing = validate_recipe(recipe)
    assert missing == ["external_id"]


def test_fields_as_schema_json_is_valid_json():
    schema_str = fields_as_schema_json()
    data = json.loads(schema_str)
    assert isinstance(data, dict)
    assert "external_id" in data
    assert "price_aed" in data
    assert "title" in data
    assert len(data) == 10
