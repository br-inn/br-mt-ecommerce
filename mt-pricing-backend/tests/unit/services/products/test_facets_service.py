"""Wave 10 — facets_service.build_product_clauses tests.

Verifica que el clause builder honra `exclude` (refinement no destructivo)
y que ProductFilters detecta filtros activos correctamente.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from app.services.products.facets_service import (
    ProductFilters,
    build_product_clauses,
)


# ---- ProductFilters DTO -------------------------------------------------------


def test_filters_defaults_no_active() -> None:
    f = ProductFilters()
    assert f.has_any_active() is False


def test_filters_active_when_any_set() -> None:
    assert ProductFilters(family="valve").has_any_active()
    assert ProductFilters(material="brass").has_any_active()
    assert ProductFilters(active=True).has_any_active()
    assert ProductFilters(search="ball").has_any_active()


def test_filters_from_dict_subset() -> None:
    f = ProductFilters.from_dict({"family": "valve", "ignored": "x", "dn": "15"})
    assert f.family == "valve"
    assert f.dn == "15"


# ---- build_product_clauses ----------------------------------------------------


def test_clauses_empty_filters_only_soft_delete() -> None:
    clauses = build_product_clauses(ProductFilters())
    # Just `deleted_at IS NULL`
    assert len(clauses) == 1


def test_clauses_include_deleted() -> None:
    clauses = build_product_clauses(ProductFilters(include_deleted=True))
    assert len(clauses) == 0


def test_clauses_with_family() -> None:
    clauses = build_product_clauses(ProductFilters(family="valve"))
    assert len(clauses) == 2  # deleted_at + family


def test_clauses_exclude_dimension_drops_clause() -> None:
    f = ProductFilters(family="valve", material="brass")
    full = build_product_clauses(f)
    excluded = build_product_clauses(f, exclude={"family"})
    assert len(full) == 3  # deleted_at + family + material
    assert len(excluded) == 2  # deleted_at + material


def test_clauses_active_false_included() -> None:
    f = ProductFilters(active=False)
    clauses = build_product_clauses(f)
    assert len(clauses) == 2


def test_clauses_has_image_true() -> None:
    f = ProductFilters(has_image=True)
    clauses = build_product_clauses(f)
    assert len(clauses) == 2  # deleted_at + image_status != missing


def test_clauses_has_image_false() -> None:
    f = ProductFilters(has_image=False)
    clauses = build_product_clauses(f)
    assert len(clauses) == 2  # deleted_at + image_status == missing


def test_clauses_search_uses_ilike_or() -> None:
    f = ProductFilters(search="ball")
    clauses = build_product_clauses(f)
    assert len(clauses) == 2  # deleted_at + (sku ILIKE OR name_en ILIKE)


def test_clauses_translation_status_uses_subquery() -> None:
    f = ProductFilters(translation_status="approved", translation_lang="es")
    clauses = build_product_clauses(f)
    assert len(clauses) == 2  # deleted_at + sku IN (sub)


def test_clauses_created_range() -> None:
    f = ProductFilters(
        created_after=datetime(2026, 1, 1),
        created_before=datetime(2026, 12, 31),
    )
    clauses = build_product_clauses(f)
    assert len(clauses) == 3  # deleted_at + after + before


def test_clauses_exclude_unknown_dimension_noop() -> None:
    f = ProductFilters(family="valve")
    clauses_with_bogus = build_product_clauses(f, exclude={"nonexistent"})
    clauses_default = build_product_clauses(f)
    assert len(clauses_with_bogus) == len(clauses_default)
