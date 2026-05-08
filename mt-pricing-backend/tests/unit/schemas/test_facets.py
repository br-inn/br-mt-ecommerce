"""Wave 10 — facets response schema tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.schemas.facets import FacetBucket, FacetsResponse, TranslationLangFacet


def test_facet_bucket_basic() -> None:
    b = FacetBucket(value="valve", count=823)
    assert b.value == "valve"
    assert b.count == 823


def test_facet_bucket_negative_count_rejected() -> None:
    with pytest.raises(ValidationError):
        FacetBucket(value="x", count=-1)


def test_translation_lang_facet_defaults() -> None:
    t = TranslationLangFacet()
    assert t.approved == 0 and t.pending == 0 and t.draft == 0 and t.missing == 0


def test_translation_lang_facet_negative_rejected() -> None:
    with pytest.raises(ValidationError):
        TranslationLangFacet(approved=-1)


def test_facets_response_shape() -> None:
    r = FacetsResponse(
        total=823,
        total_unfiltered=5085,
        family=[FacetBucket(value="valve", count=823)],
        material=[FacetBucket(value="brass", count=200)],
        dn=[FacetBucket(value="50", count=50)],
        pn=[FacetBucket(value="16", count=300)],
        data_quality={"complete": 100, "partial": 723},
        active={"True": 800, "False": 23},
        image_status={"missing": 823},
        has_image={"with": 0, "without": 823},
        translation_status={
            "es": TranslationLangFacet(missing=823),
            "ar": TranslationLangFacet(missing=823),
        },
    )
    assert r.total == 823
    assert r.total_unfiltered == 5085
    assert r.translation_status["es"].missing == 823


def test_facets_response_extra_forbidden() -> None:
    with pytest.raises(ValidationError):
        FacetsResponse(
            total=0,
            total_unfiltered=0,
            extra_field="should_fail",  # type: ignore[call-arg]
        )


def test_facets_response_optional_lists_default_empty() -> None:
    r = FacetsResponse(total=0, total_unfiltered=0)
    assert r.family == []
    assert r.material == []
    assert r.dn == []
    assert r.pn == []
    assert r.data_quality == {}
