"""Schema canónico de campos para scrapers — todos los adapters deben alinearse a estos campos."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanonicalField:
    name: str
    required: bool
    type: str
    description: str


CANONICAL_FIELDS: list[CanonicalField] = [
    CanonicalField(
        "external_id", True, "str", "Unique product ID on that site (ASIN, SKU, URL path segment)"
    ),
    CanonicalField("title", True, "str", "Product name"),
    CanonicalField(
        "price_aed", True, "currency", "Current price in AED (numeric only, no currency symbol)"
    ),
    CanonicalField("brand", False, "str", "Brand or manufacturer name"),
    CanonicalField("image_url", False, "str", "Main product image URL (absolute)"),
    CanonicalField("delivery_text", False, "str", "Delivery or shipping info text"),
    CanonicalField("rating", False, "float", "Numeric rating score (e.g. 4.5)"),
    CanonicalField("review_count", False, "int", "Number of customer reviews"),
    CanonicalField(
        "availability", False, "str", "Stock status text (e.g. 'In Stock', 'Out of Stock')"
    ),
    CanonicalField(
        "original_price_aed", False, "currency", "Original price before discount in AED"
    ),
]

REQUIRED_FIELDS: set[str] = {f.name for f in CANONICAL_FIELDS if f.required}


def validate_recipe(recipe: dict[str, Any]) -> list[str]:
    """Returns list of required field names missing from the recipe."""
    present = {f["name"] for f in recipe.get("fields", [])}
    return [name for name in sorted(REQUIRED_FIELDS) if name not in present]


def fields_as_schema_json() -> str:
    """JSON string describing all canonical fields — injected into Claude's prompt."""
    return json.dumps(
        {f.name: f"({f.type}) {f.description}" for f in CANONICAL_FIELDS},
        indent=2,
    )
