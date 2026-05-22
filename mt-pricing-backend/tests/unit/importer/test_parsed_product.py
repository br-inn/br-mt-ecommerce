"""Tests para ParsedProduct dataclass."""
from __future__ import annotations
from app.services.importer.parsed_product import ParsedProduct


def test_defaults_are_empty_collections():
    p = ParsedProduct(sku="MT-001")
    assert p.scalars == {}
    assert p.jsonb == {"dimensions": {}, "packaging": {}, "specs": {}}
    assert p.translations == {}
    assert p.certifications == []
    assert p.errors == []


def test_is_error_row_when_sku_empty():
    p = ParsedProduct(sku="", errors=["SKU vacío"])
    assert p.is_error_row is True


def test_is_not_error_row_when_sku_present():
    p = ParsedProduct(sku="MT-001")
    assert p.is_error_row is False


def test_has_translations():
    p = ParsedProduct(sku="MT-001", translations={"en": "Ball valve", "es": "Válvula"})
    assert p.has_translations is True


def test_has_certifications():
    p = ParsedProduct(sku="MT-001", certifications=["CE", "ISO 9001"])
    assert len(p.certifications) == 2
