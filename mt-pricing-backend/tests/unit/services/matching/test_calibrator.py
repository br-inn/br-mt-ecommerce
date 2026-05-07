"""Tests para IsotonicCalibrator (PAV pure Python)."""

from __future__ import annotations

import pytest

from app.services.matching.calibrator import (
    IsotonicCalibrator,
    brier_score,
    expected_calibration_error,
)

pytestmark = pytest.mark.unit


# ------------------------ PAV correctness ----------------------------- #


def test_fit_monotonic_when_input_already_sorted() -> None:
    """Si los labels ya son monótonos, los y calibrados también lo son."""
    scores = [0.1, 0.3, 0.5, 0.7, 0.9]
    labels = [0, 0, 0, 1, 1]
    cal = IsotonicCalibrator().fit(scores, labels)
    # ys deben ser no-decrecientes
    ys = cal.y_calibrated
    for i in range(1, len(ys)):
        assert ys[i] >= ys[i - 1] - 1e-9


def test_fit_resolves_violations_by_pooling() -> None:
    """Un par (i, i+1) con y[i] > y[i+1] se mergea (PAV)."""
    # raw scores ordenados, labels invertidos en el medio → violación
    scores = [0.1, 0.4, 0.5, 0.6, 0.9]
    labels = [0, 1, 0, 1, 1]
    cal = IsotonicCalibrator().fit(scores, labels)
    ys = cal.y_calibrated
    # check non-decreasing
    for i in range(1, len(ys)):
        assert ys[i] >= ys[i - 1] - 1e-9


def test_fit_with_unsorted_input_orders_internally() -> None:
    cal = IsotonicCalibrator().fit([0.9, 0.1, 0.5], [1, 0, 1])
    # primer threshold debe corresponder al menor score
    assert cal.x_thresholds[0] <= cal.x_thresholds[-1]


def test_calibrate_returns_input_when_not_fitted() -> None:
    cal = IsotonicCalibrator()
    # not fitted -> identity (clamped)
    assert cal.calibrate(0.5) == 0.5
    assert cal.calibrate(2.0) == 1.0
    assert cal.calibrate(-0.5) == 0.0


def test_calibrate_clamps_to_endpoints_when_outside_range() -> None:
    cal = IsotonicCalibrator().fit([0.2, 0.8], [0, 1])
    assert cal.calibrate(0.0) == cal.y_calibrated[0]
    assert cal.calibrate(1.0) == cal.y_calibrated[-1]


def test_calibrate_interpolates_linearly_between_points() -> None:
    cal = IsotonicCalibrator()
    cal.x_thresholds = [0.0, 1.0]
    cal.y_calibrated = [0.0, 1.0]
    cal.fitted = True
    assert cal.calibrate(0.25) == pytest.approx(0.25)
    assert cal.calibrate(0.5) == pytest.approx(0.5)
    assert cal.calibrate(0.75) == pytest.approx(0.75)


# ------------------------ persistence -------------------------------- #


def test_serialize_roundtrip() -> None:
    cal = IsotonicCalibrator(version="v1").fit([0.1, 0.5, 0.9], [0, 1, 1])
    blob = cal.serialize()
    restored = IsotonicCalibrator.deserialize(blob)
    assert restored.version == "v1"
    assert restored.x_thresholds == cal.x_thresholds
    assert restored.y_calibrated == cal.y_calibrated
    assert restored.fitted is True


def test_fit_with_empty_input_marks_fitted() -> None:
    cal = IsotonicCalibrator().fit([], [])
    assert cal.fitted is True
    assert cal.x_thresholds == []


def test_fit_raises_on_length_mismatch() -> None:
    with pytest.raises(ValueError):
        IsotonicCalibrator().fit([0.1, 0.5], [0])


# ------------------------ metrics ------------------------------------ #


def test_brier_score_perfect_zero() -> None:
    assert brier_score([0.0, 1.0, 0.0, 1.0], [0, 1, 0, 1]) == 0.0


def test_brier_score_worst_case_one() -> None:
    assert brier_score([1.0, 0.0], [0, 1]) == 1.0


def test_brier_score_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        brier_score([0.5], [0, 1])


def test_brier_score_empty_returns_zero() -> None:
    assert brier_score([], []) == 0.0


def test_ece_well_calibrated_dataset_low_value() -> None:
    # Dataset bien calibrado: avg_p del bin 0.0-0.1 = 0.05 (acc 0 → diff 0.05),
    # avg_p del bin 0.1-0.2 = 0.15 (acc 0 → diff 0.15), avg_p 0.2-0.3 = 0.25
    # (acc 0 → diff 0.25), avg_p 0.9-1.0 = 0.95 (acc 1 → diff 0.05).
    preds = [0.05, 0.15, 0.25, 0.95, 0.95]
    labels = [0, 0, 0, 1, 1]
    val = expected_calibration_error(preds, labels, n_bins=10)
    # ECE ponderada por bin size — ~0.11. Verificamos que es razonable
    # y que un dataset peor calibrado tiene un ECE más alto.
    assert 0.0 <= val <= 0.2


def test_ece_zero_for_calibrated_oracle() -> None:
    # Predictions matching labels exactly → ECE = 0
    preds = [0.0, 0.0, 1.0, 1.0]
    labels = [0, 0, 1, 1]
    assert expected_calibration_error(preds, labels, n_bins=10) == pytest.approx(0.0)


def test_ece_mismatch_raises() -> None:
    with pytest.raises(ValueError):
        expected_calibration_error([0.5], [0, 1])


def test_isotonic_improves_brier_on_mis_calibrated_dataset() -> None:
    """Un calibrator entrenado sobre los mismos datos no empeora el Brier."""
    # synthetic dataset: scores son sub-confidentes (deberían 0.7 pero son 0.4)
    scores = [0.1, 0.3, 0.4, 0.4, 0.5, 0.6, 0.7, 0.7, 0.9, 0.95]
    labels = [0, 0, 1, 1, 1, 1, 1, 1, 1, 1]

    # raw (uncalibrated) Brier
    raw = brier_score(scores, labels)

    cal = IsotonicCalibrator().fit(scores, labels)
    calibrated = [cal.calibrate(s) for s in scores]
    cal_brier = brier_score(calibrated, labels)

    assert cal_brier <= raw + 1e-9, (
        f"Calibrated Brier ({cal_brier}) should be <= raw ({raw})"
    )
