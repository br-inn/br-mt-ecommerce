"""Unit tests for `app.services.matching.scoring`.

Cobertura:
- G1: mediana × 1.10 con valores enteros e impares.
- G1 vacío → None.
- G2: coste × multiplicador default / stainless / cast_iron.
- G2 con coste 0 → None.
- compute_scoring devuelve int 0-100.
- compute_scoring detecta mismatches críticos en `notes`.
- compute_scoring perfecto match (mismo SKU vs candidato) → score alto (≥85).
- compute_scoring sin nada en común → score bajo (<40).
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.services.matching.scoring import (
    G1_MEDIAN_MULTIPLIER,
    G2_MULTIPLIERS,
    compute_g1_target,
    compute_g2_target,
    compute_scoring,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# G1
# ---------------------------------------------------------------------------
def test_g1_returns_median_times_1_10() -> None:
    # Mediana de [100,150,200] = 150 → × 1.10 = 165.00
    out = compute_g1_target([100, 150, 200])
    assert out == Decimal("165.00")


def test_g1_with_two_values_takes_average_then_multiplies() -> None:
    # [100, 200] median 150 × 1.10 = 165
    out = compute_g1_target([100, 200])
    assert out == Decimal("165.00")


def test_g1_empty_list_returns_none() -> None:
    assert compute_g1_target([]) is None


def test_g1_zeroes_filtered() -> None:
    # Single positive 100 → median 100 × 1.10 = 110
    out = compute_g1_target([0, 0, 100])
    assert out == Decimal("110.00")


def test_g1_constant_matches_doc() -> None:
    assert G1_MEDIAN_MULTIPLIER == Decimal("1.10")


# ---------------------------------------------------------------------------
# G2
# ---------------------------------------------------------------------------
def test_g2_default_material() -> None:
    out = compute_g2_target(100, material="brass")
    assert out == Decimal("250.00")  # 100 × 2.5


def test_g2_stainless_subtype_detected_from_material() -> None:
    out = compute_g2_target(100, material="ss316")
    assert out == Decimal("280.00")  # 100 × 2.8


def test_g2_cast_iron_subtype() -> None:
    out = compute_g2_target(50, material="cast_iron")
    assert out == Decimal("150.00")  # 50 × 3.0


def test_g2_explicit_subtype_overrides_detection() -> None:
    out = compute_g2_target(100, material="brass", subtype="cast_iron")
    assert out == Decimal("300.00")


def test_g2_zero_cost_returns_none() -> None:
    assert compute_g2_target(0, material="brass") is None


def test_g2_negative_cost_returns_none() -> None:
    assert compute_g2_target(-1, material="brass") is None


def test_g2_multipliers_match_doc() -> None:
    assert G2_MULTIPLIERS["default"] == Decimal("2.5")
    assert G2_MULTIPLIERS["stainless"] == Decimal("2.8")
    assert G2_MULTIPLIERS["cast_iron"] == Decimal("3.0")


# ---------------------------------------------------------------------------
# Scoring 0-100
# ---------------------------------------------------------------------------
def _sku_pegler() -> dict:
    return {
        "sku": "MTBR4001050",
        "material": "brass",
        "pn": "PN25",
        "thread": "BSP",
        "norma": "EN13828",
        "brand": "Pegler",
    }


def test_score_perfect_match_is_high() -> None:
    sku = _sku_pegler()
    candidate = {
        "material": "brass",
        "pn": "PN25",
        "thread": "BSP",
        "norma": "EN13828",
        "brand": "Pegler",
        "delivery_text": "next day",
    }
    result = compute_scoring(sku, candidate)
    assert 90 <= result.score <= 100


def test_score_returns_int_in_range() -> None:
    result = compute_scoring(_sku_pegler(), {"material": None})
    assert isinstance(result.score, int)
    assert 0 <= result.score <= 100


def test_score_pn_below_requirement_blocks_score() -> None:
    sku = _sku_pegler()
    candidate = {
        "material": "brass",
        "pn": "PN10",  # below SKU PN25
        "thread": "BSP",
        "norma": "EN13828",
        "brand": "Pegler",
        "delivery_text": "next day",
    }
    result = compute_scoring(sku, candidate)
    assert "pn_below_sku_requirement" in result.notes


def test_score_thread_mismatch_flagged() -> None:
    sku = _sku_pegler()
    candidate = {
        "material": "brass",
        "pn": "PN25",
        "thread": "NPT",  # mismatch BSP
        "norma": "EN13828",
        "brand": "Pegler",
    }
    result = compute_scoring(sku, candidate)
    assert "thread_standard_mismatch" in result.notes


def test_score_breakdown_contains_all_dimensions() -> None:
    result = compute_scoring(_sku_pegler(), {"material": "brass"})
    expected = {"material", "pn", "thread_standard", "norma", "brand_tier", "delivery"}
    assert expected <= set(result.breakdown.keys())


def test_score_partial_brand_match_via_tier() -> None:
    sku = _sku_pegler()
    sku["brand"] = "MT-Brand"
    candidate = {
        "material": "brass",
        "pn": "PN25",
        "thread": "BSP",
        "norma": "EN13828",
        "brand": "Apollo",  # tier1
        "delivery_text": "2 days",
    }
    result = compute_scoring(sku, candidate)
    # Brand_tier debe ser 0.7 (tier1 fallback)
    assert result.breakdown["brand_tier"] == pytest.approx(0.7, abs=0.01)


def test_score_completely_different_is_low() -> None:
    sku = _sku_pegler()
    candidate = {
        "material": "pvc",
        "pn": "PN6",
        "thread": "FLANGED",
        "norma": "ISO9999",
        "brand": "UnknownBrand",
        "delivery_text": "3-4 weeks",
    }
    result = compute_scoring(sku, candidate)
    assert result.score < 40


def test_score_uses_specs_dict_when_top_level_missing() -> None:
    sku = _sku_pegler()
    candidate = {
        "specs": {
            "material": "brass",
            "pn": "PN25",
            "thread": "BSP",
            "norma": "EN13828",
        },
        "brand": "Pegler",
        "delivery_text": "next day",
    }
    result = compute_scoring(sku, candidate)
    assert result.score >= 90
