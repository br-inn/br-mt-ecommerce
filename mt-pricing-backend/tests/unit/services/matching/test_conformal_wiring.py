"""Verifica que populate_conformal escribe las columnas conformal."""
from __future__ import annotations

from app.services.matching.match_service import populate_conformal_fields


class _FakeCand:
    def __init__(self, score):
        self.score = score
        self.calibrated_confidence = None
        self.conf_lower = None
        self.conf_upper = None
        self.review_priority = None


def test_populate_conformal_noop_without_calibrator():
    cand = _FakeCand(score=70)
    populate_conformal_fields(cand, calibrator=None)
    assert cand.review_priority is None
    assert cand.conf_lower is None


def test_populate_conformal_sets_fields_with_calibrator():
    from app.services.matching.calibrator import ConformalWrapper, IsotonicCalibrator

    cal = IsotonicCalibrator().fit([0.1, 0.5, 0.9] * 100, [0, 0, 1] * 100)
    wrapper = ConformalWrapper(calibrator=cal, method="venn_abers")
    wrapper.fit([0.1, 0.5, 0.9] * 100, [0, 0, 1] * 100)
    cand = _FakeCand(score=90)
    populate_conformal_fields(cand, calibrator=wrapper)
    assert cand.calibrated_confidence is not None
    assert cand.conf_lower is not None
    assert cand.conf_upper is not None
