"""Unit tests for series_resolver — pure functions only (no DB)."""
import pytest
from app.services.ficha_enrichment.series_resolver import (
    extract_series_prefix,
    dn_label_to_int,
    generate_candidate_skus,
)
from app.schemas.ficha_enrich import (
    FichaExtractionResult,
    ExtractedScalars,
    ExtractedSpecs,
    ExtractedDimensionRow,
)


def _make_extraction(dn_labels: list[str]) -> FichaExtractionResult:
    return FichaExtractionResult(
        scalars=ExtractedScalars(),
        specs=ExtractedSpecs(),
        dimensions=[ExtractedDimensionRow(dn_label=lbl, values={}) for lbl in dn_labels],
        confidence=0.9,
    )


def test_extract_series_prefix_standard():
    assert extract_series_prefix("MTFT_4097.pdf") == "4097"


def test_extract_series_prefix_dash():
    assert extract_series_prefix("MTFT-4097.pdf") == "4097"


def test_extract_series_prefix_no_match():
    assert extract_series_prefix("random.pdf") is None


def test_dn_label_to_int_dn_prefix():
    assert dn_label_to_int("DN15") == 15
    assert dn_label_to_int("DN 25") == 25


def test_dn_label_to_int_imperial():
    assert dn_label_to_int('1/2"') == 15
    assert dn_label_to_int('1"') == 25
    assert dn_label_to_int('1-1/2"') == 40


def test_dn_label_to_int_numeric():
    assert dn_label_to_int("15") == 15
    assert dn_label_to_int("50") == 50


def test_generate_candidate_skus():
    extraction = _make_extraction(['1/2"', '3/4"', '1"'])
    skus = generate_candidate_skus("4097", extraction)
    assert skus == ["4097015", "4097020", "4097025"]


def test_generate_candidate_skus_dn_labels():
    extraction = _make_extraction(["DN15", "DN20", "DN25"])
    skus = generate_candidate_skus("4097", extraction)
    assert skus == ["4097015", "4097020", "4097025"]


def test_generate_candidate_skus_empty_dims():
    extraction = _make_extraction([])
    skus = generate_candidate_skus("4097", extraction)
    assert skus == []
