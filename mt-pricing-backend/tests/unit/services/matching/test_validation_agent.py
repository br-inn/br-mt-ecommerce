"""Tests de la función de decisión del MatchValidationAgent."""

from __future__ import annotations

from app.services.matching.validation_agent import AgentDecision, decide_verdict


def test_bootstrap_auto_validate_from_enhanced():
    d = decide_verdict(
        score=80,
        enhanced={"auto_validate": True, "method": "deterministic"},
        review_priority=None,
        has_calibrator=False,
    )
    assert d == AgentDecision(verdict="auto_validate", signal="bootstrap")


def test_bootstrap_vision_rejected_is_auto_discard():
    d = decide_verdict(
        score=0,
        enhanced={"auto_validate": False, "method": "vision_rejected"},
        review_priority=None,
        has_calibrator=False,
    )
    assert d.verdict == "auto_discard"


def test_bootstrap_human_queue_when_uncertain():
    d = decide_verdict(
        score=55,
        enhanced={"auto_validate": False, "method": "human_queue"},
        review_priority=None,
        has_calibrator=False,
    )
    assert d.verdict == "human"


def test_conformal_low_priority_auto_validates():
    d = decide_verdict(
        score=70,
        enhanced={"auto_validate": False, "method": "human_queue"},
        review_priority="low",
        has_calibrator=True,
    )
    assert d == AgentDecision(verdict="auto_validate", signal="conformal")


def test_conformal_high_priority_auto_discards():
    d = decide_verdict(
        score=40,
        enhanced={"auto_validate": False, "method": "human_queue"},
        review_priority="high",
        has_calibrator=True,
    )
    assert d.verdict == "auto_discard"


def test_conformal_gray_band_goes_to_human():
    d = decide_verdict(
        score=50,
        enhanced={"auto_validate": False, "method": "human_queue"},
        review_priority=None,
        has_calibrator=True,
    )
    assert d.verdict == "human"


def test_conformal_vision_rejected_still_discards():
    d = decide_verdict(
        score=0,
        enhanced={"auto_validate": False, "method": "vision_rejected"},
        review_priority="low",
        has_calibrator=True,
    )
    assert d.verdict == "auto_discard"
