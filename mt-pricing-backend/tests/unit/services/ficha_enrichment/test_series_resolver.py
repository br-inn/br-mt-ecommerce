"""Unit tests for series_resolver — pure functions only (no DB)."""

import pytest
from app.services.ficha_enrichment.series_resolver import (
    extract_series_prefix,
    extract_all_series_from_text,
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


# ---------------------------------------------------------------------------
# extract_all_series_from_text
# ---------------------------------------------------------------------------


def test_extract_all_series_single_pair():
    text = "4097 / 40972 Pag. 3/9"
    result = extract_all_series_from_text(text)
    assert result == [("4097", "40972")]


def test_extract_all_series_multi_pair():
    text = "4295 / 42952 Pag. 1/9\n4097 / 40972 Pag. 3/9\n4098 / 40982 Pag. 5/9\n"
    result = extract_all_series_from_text(text)
    assert ("4295", "42952") in result
    assert ("4097", "40972") in result
    assert ("4098", "40982") in result
    assert len(result) == 3


def test_extract_all_series_no_false_positive_page_numbers():
    text = 'Pag. 3/9\nDN 1/2"\n'
    result = extract_all_series_from_text(text)
    assert result == []


def test_extract_all_series_independent_series():
    text = "4100 / 4200 ver especificaciones"
    result = extract_all_series_from_text(text)
    # Neither is a color variant of the other (4200 != 4100 + "2")
    assert ("4100", None) in result
    assert ("4200", None) in result


def test_extract_all_series_deduplicates():
    text = "4097 / 40972 Pag. 3/9\n4097 / 40972 Pag. 4/9\n"
    result = extract_all_series_from_text(text)
    assert len(result) == 1
    assert result[0] == ("4097", "40972")


def test_extract_all_series_empty_text():
    assert extract_all_series_from_text("") == []
