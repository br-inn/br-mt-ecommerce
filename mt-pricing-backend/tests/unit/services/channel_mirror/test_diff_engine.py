"""Tests del diff engine — pure functions, no IO."""

from __future__ import annotations

import pytest

from app.services.channel_mirror.diff_engine import (
    DIFF_STATUS_DRIFT,
    DIFF_STATUS_MATCH,
    DIFF_STATUS_MISSING,
    DIFF_STATUS_QUEUED,
    canonical_vs_live,
    summarize,
)

pytestmark = pytest.mark.unit


def test_match_when_values_equal() -> None:
    canonical = {"brand": "Genebre", "DN": "25 mm"}
    live = {"brand": "Genebre", "DN": "25 mm"}
    diffs = canonical_vs_live(canonical, live)
    assert all(d.status == DIFF_STATUS_MATCH for d in diffs)
    assert len(diffs) == 2


def test_drift_when_values_differ() -> None:
    canonical = {"material": "Brass CW617N"}
    live = {"material": "Brass"}
    diffs = canonical_vs_live(canonical, live)
    assert len(diffs) == 1
    assert diffs[0].status == DIFF_STATUS_DRIFT
    assert diffs[0].mt == "Brass CW617N"
    assert diffs[0].live == "Brass"


def test_missing_when_live_empty() -> None:
    canonical = {"title_ar": "صمام كروي PN16"}
    live = {"title_ar": ""}
    diffs = canonical_vs_live(canonical, live)
    assert diffs[0].status == DIFF_STATUS_MISSING
    # AR detection — el field acaba en _ar
    assert diffs[0].lang == "ar"


def test_missing_when_live_key_absent() -> None:
    canonical = {"bullet_2": "16 bar"}
    live: dict[str, object] = {}
    diffs = canonical_vs_live(canonical, live)
    assert diffs[0].status == DIFF_STATUS_MISSING


def test_match_when_both_empty() -> None:
    canonical = {"description_ar": None}
    live = {"description_ar": ""}
    diffs = canonical_vs_live(canonical, live)
    assert diffs[0].status == DIFF_STATUS_MATCH


def test_queued_overrides_other_states() -> None:
    canonical = {"image_4 (AR)": "img/x_ar.jpg"}
    live: dict[str, object] = {"image_4 (AR)": ""}
    diffs = canonical_vs_live(
        canonical, live, queued_fields={"image_4 (AR)"}
    )
    assert diffs[0].status == DIFF_STATUS_QUEUED
    # AR detection from "(AR)" suffix
    assert diffs[0].lang == "ar"


def test_normalization_handles_whitespace_and_case() -> None:
    canonical = {"brand": "Genebre"}
    live = {"brand": "  GENEBRE   "}
    diffs = canonical_vs_live(canonical, live)
    assert diffs[0].status == DIFF_STATUS_MATCH


def test_field_order_preserved_canonical_first() -> None:
    canonical = {"title_en": "A", "brand": "B"}
    live = {"price": "10", "title_en": "A"}
    diffs = canonical_vs_live(canonical, live)
    fields = [d.field for d in diffs]
    # canonical primero, luego live-only
    assert fields[:2] == ["title_en", "brand"]
    assert "price" in fields


def test_explicit_fields_order_filters_keys() -> None:
    canonical = {"a": "1", "b": "2", "c": "3"}
    live = {"a": "1", "b": "X"}
    diffs = canonical_vs_live(canonical, live, fields_order=["b", "a"])
    fields = [d.field for d in diffs]
    assert fields == ["b", "a"]


def test_summary_counts() -> None:
    canonical = {"a": "x", "b": "y", "c": "z", "d": "w"}
    live = {"a": "x", "b": "different", "c": ""}
    diffs = canonical_vs_live(
        canonical, live, queued_fields={"d"}
    )
    counts = summarize(diffs)
    assert counts["match"] == 1
    assert counts["drift"] == 1
    assert counts["missing"] == 1
    assert counts["queued"] == 1


def test_mono_flag_for_known_fields() -> None:
    canonical = {"HS_code": "8481.80.81", "DN": "25 mm", "title_en": "x"}
    live = {"HS_code": "8481.80.81", "DN": "25 mm", "title_en": "x"}
    diffs = canonical_vs_live(canonical, live)
    by_field = {d.field: d for d in diffs}
    assert by_field["HS_code"].mono is True
    assert by_field["DN"].mono is True
    assert by_field["title_en"].mono is False


def test_to_dict_shape() -> None:
    canonical = {"brand": "Genebre"}
    live = {"brand": "Other"}
    diff = canonical_vs_live(canonical, live)[0]
    d = diff.to_dict()
    assert d["field"] == "brand"
    assert d["status"] == DIFF_STATUS_DRIFT
    assert d["mt"] == "Genebre"
    assert d["live"] == "Other"
    assert "lang" in d and "mono" in d


def test_mockup_scenario_replays_frontend_states() -> None:
    """Reproduce el mockup MIRROR_ROWS y verifica los status esperados."""
    canonical = {
        "title_en": "Ball valve PN16, DN25, brass CW617N",
        "title_ar": "صمام كروي PN16, مقاس DN25, نحاس CW617N",
        "bullet_1": "2-piece body, full bore, BSP F/F",
        "bullet_2": "Suitable for water + inert gas, ≤16 bar / 80 °C",
        "brand": "Genebre",
        "HS_code": "8481.80.81",
        "material": "Brass CW617N",
        "DN": "25 mm",
        "PN": "16 bar",
        "weight": "0,38 kg",
        "price_aed": "147,75 AED",
        "image_main": "img/MTV-1004_main.jpg (1500×1500)",
        "image_4 (AR)": "img/MTV-1004_4_ar.jpg",
    }
    live = {
        "title_en": "Ball Valve PN16 DN25 Brass — MT",
        "title_ar": "",
        "bullet_1": "2-piece body, full bore, BSP F/F",
        "bullet_2": "Suitable for water, ≤10 bar / 80 °C",
        "brand": "Genebre",
        "HS_code": "8481.80.81",
        "material": "Brass",
        "DN": "25 mm",
        "PN": "16 bar",
        "weight": "0,38 kg",
        "price_aed": "147,75 AED",
        "image_main": "amazon-cdn/.../71kQ_…",
        "image_4 (AR)": "",
    }
    diffs = canonical_vs_live(
        canonical, live, queued_fields={"image_4 (AR)"}
    )
    by_field = {d.field: d.status for d in diffs}
    assert by_field["title_en"] == DIFF_STATUS_DRIFT
    assert by_field["title_ar"] == DIFF_STATUS_MISSING
    assert by_field["bullet_1"] == DIFF_STATUS_MATCH
    assert by_field["bullet_2"] == DIFF_STATUS_DRIFT
    assert by_field["brand"] == DIFF_STATUS_MATCH
    assert by_field["material"] == DIFF_STATUS_DRIFT
    # image_main: distintos URLs → drift (no match)
    assert by_field["image_main"] == DIFF_STATUS_DRIFT
    # queued field
    assert by_field["image_4 (AR)"] == DIFF_STATUS_QUEUED
