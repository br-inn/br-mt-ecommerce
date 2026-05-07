"""Unit tests para `app.services.importer_datasheets.dual_extractor` (US-1A-06-04-V2).

Inyecta callables/mocks para regex + vision — sin pdfplumber/HTTP.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from app.services.importer_datasheets.dual_extractor import (
    SPEC_KEYS,
    DualExtractor,
)
from app.services.importer_datasheets.spec_parser import DatasheetSpecs
from app.services.importer_datasheets.vision_extractor import (
    VisionExtractionResult,
)

pytestmark = pytest.mark.unit


def _mk_vision(
    specs: dict[str, Any] | None = None,
    *,
    confidence: float = 0.75,
    skipped: bool = False,
    skip_reason: str | None = None,
    error: str | None = None,
) -> Any:
    """Factory de VisionExtractor mock que devuelve un VisionExtractionResult."""
    res = VisionExtractionResult(
        specs=dict(specs or {}),
        confidence=confidence,
        skipped=skipped,
        skip_reason=skip_reason,
        error=error,
    )
    mock = AsyncMock()
    mock.extract = AsyncMock(return_value=res)
    return mock


# ---------------------------------------------------------------------------
# Regex-only path (vision skipped)
# ---------------------------------------------------------------------------
async def test_regex_only_when_vision_skipped() -> None:
    def _regex(_b: bytes) -> DatasheetSpecs:
        return DatasheetSpecs(dn="DN50", pn="PN16", material="brass")

    vision_mock = _mk_vision(skipped=True, skip_reason="vision_disabled_live_network_off")
    extractor = DualExtractor(regex_extractor=_regex, vision_extractor=vision_mock)

    res = await extractor.extract(pdf_bytes=b"%PDF", filename="MTFT_5114.pdf")
    assert res.specs["dn"] == "DN50"
    assert res.specs["pn"] == "PN16"
    assert res.specs["material"] == "brass"
    assert res.disagreement is False
    assert res.vision_skipped is True
    # Confidence == regex hit confidence ≈ 0.7
    assert res.overall_confidence == pytest.approx(0.7)


# ---------------------------------------------------------------------------
# Vision-only path (regex empty)
# ---------------------------------------------------------------------------
async def test_vision_only_when_regex_empty() -> None:
    def _regex(_b: bytes) -> DatasheetSpecs:
        return DatasheetSpecs()  # empty

    vision_mock = _mk_vision(
        {"dn": "DN65", "pn": "PN25", "material": "ss316"}, confidence=0.9
    )
    extractor = DualExtractor(regex_extractor=_regex, vision_extractor=vision_mock)

    res = await extractor.extract(pdf_bytes=b"%PDF", filename="x.pdf")
    assert res.specs["dn"] == "DN65"
    assert res.specs["pn"] == "PN25"
    assert res.specs["material"] == "ss316"
    assert res.disagreement is False
    assert res.overall_confidence == pytest.approx(0.9)


# ---------------------------------------------------------------------------
# Agreement: confidence boost
# ---------------------------------------------------------------------------
async def test_agreement_uses_max_confidence() -> None:
    def _regex(_b: bytes) -> DatasheetSpecs:
        return DatasheetSpecs(dn="DN50", material="brass")

    vision_mock = _mk_vision(
        {"dn": "DN50", "material": "brass", "pn": "PN16"}, confidence=0.85
    )
    extractor = DualExtractor(regex_extractor=_regex, vision_extractor=vision_mock)

    res = await extractor.extract(pdf_bytes=b"%PDF", filename="x.pdf")
    assert res.disagreement is False
    # dn + material agree (max(0.7, 0.85) = 0.85), pn vision-only (0.85)
    assert res.per_spec_confidence["dn"] == pytest.approx(0.85)
    assert res.per_spec_confidence["material"] == pytest.approx(0.85)
    assert res.per_spec_confidence["pn"] == pytest.approx(0.85)


# ---------------------------------------------------------------------------
# Disagreement: vision wins, confidence penalized
# ---------------------------------------------------------------------------
async def test_disagreement_vision_wins_with_penalty() -> None:
    def _regex(_b: bytes) -> DatasheetSpecs:
        return DatasheetSpecs(dn="DN50")

    vision_mock = _mk_vision({"dn": "DN65"}, confidence=0.8)
    extractor = DualExtractor(regex_extractor=_regex, vision_extractor=vision_mock)

    res = await extractor.extract(pdf_bytes=b"%PDF", filename="x.pdf")
    assert res.specs["dn"] == "DN65"  # vision wins
    assert res.disagreement is True
    # Penalty 0.2 → 0.8 - 0.2 = 0.6
    assert res.per_spec_confidence["dn"] == pytest.approx(0.6)


async def test_disagreement_normalization_treats_case_as_equal() -> None:
    """DN50 == dn50 — no debe contar como disagreement."""

    def _regex(_b: bytes) -> DatasheetSpecs:
        return DatasheetSpecs(dn="DN50")

    vision_mock = _mk_vision({"dn": "dn50"}, confidence=0.8)
    extractor = DualExtractor(regex_extractor=_regex, vision_extractor=vision_mock)

    res = await extractor.extract(pdf_bytes=b"%PDF", filename="x.pdf")
    assert res.disagreement is False


# ---------------------------------------------------------------------------
# Vision contributes extras (regex doesn't)
# ---------------------------------------------------------------------------
async def test_vision_extra_dict_merged() -> None:
    def _regex(_b: bytes) -> DatasheetSpecs:
        return DatasheetSpecs(dn="DN50")

    vision_mock = _mk_vision(
        {"dn": "DN50", "extra": {"weight_kg": "12", "port": "DN50"}},
        confidence=0.7,
    )
    extractor = DualExtractor(regex_extractor=_regex, vision_extractor=vision_mock)

    res = await extractor.extract(pdf_bytes=b"%PDF", filename="x.pdf")
    assert "extra" in res.specs
    assert res.specs["extra"]["weight_kg"] == "12"


# ---------------------------------------------------------------------------
# Failure handling
# ---------------------------------------------------------------------------
async def test_regex_exception_doesnt_break_when_vision_provides() -> None:
    def _broken_regex(_b: bytes) -> DatasheetSpecs:
        raise RuntimeError("regex died")

    vision_mock = _mk_vision({"dn": "DN50"}, confidence=0.9)
    extractor = DualExtractor(
        regex_extractor=_broken_regex, vision_extractor=vision_mock
    )
    res = await extractor.extract(pdf_bytes=b"%PDF", filename="x.pdf")
    assert res.error is not None
    assert "regex_failed" in res.error
    assert res.specs["dn"] == "DN50"  # vision saved the day


async def test_vision_exception_falls_back_to_regex() -> None:
    def _regex(_b: bytes) -> DatasheetSpecs:
        return DatasheetSpecs(dn="DN50", material="brass")

    flaky_vision = AsyncMock()
    flaky_vision.extract = AsyncMock(side_effect=RuntimeError("openai down"))
    extractor = DualExtractor(
        regex_extractor=_regex, vision_extractor=flaky_vision
    )
    res = await extractor.extract(pdf_bytes=b"%PDF", filename="x.pdf")
    # Aún con vision crash, regex output queda persistido.
    assert res.specs["dn"] == "DN50"
    assert res.specs["material"] == "brass"
    assert res.disagreement is False


async def test_empty_specs_overall_confidence_zero() -> None:
    def _regex(_b: bytes) -> DatasheetSpecs:
        return DatasheetSpecs()

    vision_mock = _mk_vision({}, confidence=0.0)
    extractor = DualExtractor(
        regex_extractor=_regex, vision_extractor=vision_mock
    )
    res = await extractor.extract(pdf_bytes=b"%PDF", filename="x.pdf")
    assert res.specs == {}
    assert res.overall_confidence == 0.0


# ---------------------------------------------------------------------------
# Smoke
# ---------------------------------------------------------------------------
def test_spec_keys_constant() -> None:
    assert SPEC_KEYS == ("dn", "pn", "material", "seal")
