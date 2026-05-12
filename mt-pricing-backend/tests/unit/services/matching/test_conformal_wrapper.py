"""Tests unitarios para ConformalWrapper (US-F15-03-03).

Cubre:
- test_conformal_coverage_venn_abers: cobertura empírica >= 0.98 con Venn-Abers interno
- test_insufficient_samples_raises: ValueError cuando len < 200
- test_review_priority_low: conf_lower > 0.70 → 'low'
- test_review_priority_high: conf_upper < 0.50 → 'high'
- test_review_priority_none: intervalo intermedio → None
- test_predict_interval_bounds: lower <= point <= upper, todo en [0,1]
"""

from __future__ import annotations

import random

import pytest

from app.services.matching.calibrator import (
    ConformalPrediction,
    ConformalWrapper,
    IsotonicCalibrator,
)


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #


def _make_fitted_calibrator(n: int = 600, seed: int = 42) -> IsotonicCalibrator:
    """Crea un IsotonicCalibrator ajustado sobre datos sintéticos."""
    rng = random.Random(seed)
    scores = [rng.random() for _ in range(n)]
    labels = [1 if s > 0.5 else 0 for s in scores]
    cal = IsotonicCalibrator()
    cal.fit(scores, labels)
    return cal


def _make_cal_data(
    n: int = 500,
    seed: int = 99,
) -> tuple[list[float], list[int]]:
    """Genera pares (score, label) para calibración hold-out."""
    rng = random.Random(seed)
    scores = [rng.random() for _ in range(n)]
    labels = [1 if s > 0.5 else 0 for s in scores]
    return scores, labels


# ------------------------------------------------------------------ #
# Tests
# ------------------------------------------------------------------ #


class TestConformalWrapperVennAbers:
    """Grupo de tests que fuerzan el path Venn-Abers interno (sin mapie)."""

    def _make_wrapper_venn_abers(self, cal: IsotonicCalibrator, alpha: float = 0.02) -> ConformalWrapper:
        """Crea un ConformalWrapper con method='venn_abers' (evita mapie)."""
        wrapper = ConformalWrapper(calibrator=cal, method="venn_abers", alpha=alpha)
        return wrapper

    def test_conformal_coverage_venn_abers(self) -> None:
        """Cobertura empírica >= 0.98 (tolerancia ±0.005) con 500 muestras sintéticas."""
        rng = random.Random(7)
        n_total = 1000

        # Datos para fit del calibrador base
        train_scores = [rng.random() for _ in range(n_total)]
        train_labels = [1 if s > 0.5 else 0 for s in train_scores]
        cal = IsotonicCalibrator()
        cal.fit(train_scores, train_labels)

        # Hold-out para ConformalWrapper
        cal_scores = [rng.random() for _ in range(500)]
        cal_labels = [1 if s > 0.5 else 0 for s in cal_scores]

        wrapper = self._make_wrapper_venn_abers(cal)
        wrapper.fit(cal_scores, cal_labels)

        # Test set para medir cobertura
        test_scores = [rng.random() for _ in range(500)]
        test_labels = [1 if s > 0.5 else 0 for s in test_scores]

        covered = 0
        for score, label in zip(test_scores, test_labels, strict=True):
            pred = wrapper.predict_with_interval(score)
            if pred.lower_bound <= label <= pred.upper_bound:
                covered += 1

        coverage = covered / len(test_scores)
        # Cobertura empírica debe ser >= 0.98 (con tolerancia ±0.005 → >= 0.975)
        assert coverage >= 0.975, (
            f"Cobertura empírica {coverage:.4f} < umbral 0.975"
        )

    def test_insufficient_samples_raises(self) -> None:
        """Menos de 200 muestras → ValueError."""
        cal = _make_fitted_calibrator()
        wrapper = ConformalWrapper(calibrator=cal, method="venn_abers")

        scores = [0.5] * 199
        labels = [1] * 199

        with pytest.raises(ValueError, match="Insufficient calibration samples"):
            wrapper.fit(scores, labels)

    def test_review_priority_low(self) -> None:
        """conf_lower > 0.70 → review_priority='low'."""
        cal = IsotonicCalibrator()
        # Calibrador fijo que siempre devuelve ~0.90
        cal.x_thresholds = [0.0, 1.0]
        cal.y_calibrated = [0.90, 0.90]
        cal.fitted = True

        wrapper = self._make_wrapper_venn_abers(cal, alpha=0.02)

        # Residuales muy pequeños → margen ~0.01 → lower ≈ 0.89 > 0.70
        cal_scores = [float(i) / 300 for i in range(300)]
        # Todos los labels son 1 → residuales = |1 - 0.90| = 0.10
        # Con margen ~ 0.10, lower = 0.90 - 0.10 = 0.80 > 0.70
        cal_labels = [1] * 300
        wrapper.fit(cal_scores, cal_labels)

        pred = wrapper.predict_with_interval(0.95)
        # Verificar que lower_bound > 0.70 y priority='low'
        assert pred.lower_bound > 0.70, f"Expected lower > 0.70, got {pred.lower_bound}"
        assert pred.review_priority == "low", (
            f"Expected 'low', got {pred.review_priority!r}"
        )

    def test_review_priority_high(self) -> None:
        """conf_upper < 0.50 → review_priority='high'."""
        cal = IsotonicCalibrator()
        # Calibrador fijo que siempre devuelve ~0.10
        cal.x_thresholds = [0.0, 1.0]
        cal.y_calibrated = [0.10, 0.10]
        cal.fitted = True

        wrapper = self._make_wrapper_venn_abers(cal, alpha=0.02)

        # Residuales: |0 - 0.10| = 0.10 → margin ≈ 0.10 → upper = 0.10 + 0.10 = 0.20 < 0.50
        cal_scores = [float(i) / 300 for i in range(300)]
        cal_labels = [0] * 300
        wrapper.fit(cal_scores, cal_labels)

        pred = wrapper.predict_with_interval(0.05)
        assert pred.upper_bound < 0.50, f"Expected upper < 0.50, got {pred.upper_bound}"
        assert pred.review_priority == "high", (
            f"Expected 'high', got {pred.review_priority!r}"
        )

    def test_review_priority_none(self) -> None:
        """Intervalo intermedio → review_priority=None.

        Usa un calibrador que mapea score=0.6 → 0.60, con residuales pequeños,
        de forma que lower ≈ 0.50 y upper ≈ 0.70, quedando en la zona None.
        """
        cal = IsotonicCalibrator()
        # Calibrador fijo: score=0.6 → 0.60
        cal.x_thresholds = [0.0, 1.0]
        cal.y_calibrated = [0.60, 0.60]
        cal.fitted = True

        wrapper = self._make_wrapper_venn_abers(cal, alpha=0.02)

        # Residuales ~ 0.10 → cuantil 98% ≈ 0.10 → lower=0.50, upper=0.70
        # labels alternados 0/1 → residuales: |0-0.60|=0.60 y |1-0.60|=0.40
        # → cuantil 98% ≈ 0.60 → margin = 0.60 → lower = max(0,0.0) upper = min(1,1.20) = 1.0
        # Eso da upper=1.0 >= 0.50 y lower=0.0 <= 0.70 → None ✓
        cal_scores = [float(i) / 300 for i in range(300)]
        cal_labels = [i % 2 for i in range(300)]
        wrapper.fit(cal_scores, cal_labels)

        pred = wrapper.predict_with_interval(0.6)
        # lower <= 0.70 y upper >= 0.50 → None
        assert pred.review_priority is None, (
            f"Expected None but got {pred.review_priority!r} "
            f"(lower={pred.lower_bound:.4f}, upper={pred.upper_bound:.4f}, "
            f"point={pred.point_estimate:.4f})"
        )

    def test_predict_interval_bounds(self) -> None:
        """lower_bound <= point_estimate <= upper_bound, todos en [0,1]."""
        cal = _make_fitted_calibrator(n=800, seed=77)
        wrapper = self._make_wrapper_venn_abers(cal, alpha=0.02)

        cal_scores, cal_labels = _make_cal_data(n=300, seed=88)
        wrapper.fit(cal_scores, cal_labels)

        test_scores = [i / 100.0 for i in range(0, 101)]  # 0.0, 0.01, ..., 1.0
        for score in test_scores:
            pred = wrapper.predict_with_interval(score)
            assert isinstance(pred, ConformalPrediction)
            assert 0.0 <= pred.lower_bound <= 1.0, (
                f"lower_bound={pred.lower_bound} out of [0,1] for score={score}"
            )
            assert 0.0 <= pred.upper_bound <= 1.0, (
                f"upper_bound={pred.upper_bound} out of [0,1] for score={score}"
            )
            assert 0.0 <= pred.point_estimate <= 1.0, (
                f"point_estimate={pred.point_estimate} out of [0,1] for score={score}"
            )
            assert pred.lower_bound <= pred.point_estimate + 1e-9, (
                f"lower={pred.lower_bound} > point={pred.point_estimate} for score={score}"
            )
            assert pred.upper_bound >= pred.point_estimate - 1e-9, (
                f"upper={pred.upper_bound} < point={pred.point_estimate} for score={score}"
            )
