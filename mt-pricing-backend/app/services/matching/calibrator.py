"""Isotonic Regression calibrator — pure Python, no sklearn (US-1A-09-06).

Implementación del algoritmo Pool Adjacent Violators (PAV) para calibrar
scores crudos del comparador (Etapa 6 del pipeline). Diseño:

- ``IsotonicCalibrator.fit(scores, labels)`` aprende una función monótona
  no-decreciente sobre el dataset etiquetado (0/1).
- ``calibrate(score)`` interpola lineal sobre los puntos aprendidos.
- ``serialize()`` / ``deserialize()`` para persistir el modelo en
  ``competitor_calibrators.model_artifact`` (JSON simple — sin pickle).

Por qué pure Python y no ``sklearn.isotonic``:
- Mantenemos las dependencias mínimas (sklearn pesa ~50MB).
- El algoritmo PAV cabe en ~30 líneas, fácil de auditar y testear.
- Para Brier score / ECE basta numpy si ya está; aquí computamos sin numpy.

Pipeline ref: ``mt-product-matching-pipeline-detail.md`` §8.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Literal


@dataclass
class IsotonicCalibrator:
    """Calibrator monótono no-decreciente.

    Atributos:
        x_thresholds: lista de scores ordenados de menor a mayor.
        y_calibrated: lista de probabilidades calibradas en [0,1] correspondientes.
        version: identificador semántico (e.g. ``"v1"``, ``"s4-degraded"``).
    """

    x_thresholds: list[float] = field(default_factory=list)
    y_calibrated: list[float] = field(default_factory=list)
    version: str = "v0"
    fitted: bool = False

    # ------------------------------------------------------------------ #
    # Fitting
    # ------------------------------------------------------------------ #
    def fit(self, scores: list[float], labels: list[int]) -> IsotonicCalibrator:
        """Pool Adjacent Violators.

        Args:
            scores: scores crudos (cualquier rango — típicamente 0..1).
            labels: 0/1 — match real (1) o no-match (0).

        Algoritmo:
            1. Ordenar pares (score, label) por score ascendente.
            2. PAV: mientras existan pares (i, i+1) con y_i > y_{i+1}, mergearlos
               como pool con su media ponderada y peso acumulado. Repetir hasta
               todos los y monótonos.
            3. Comprimir pools idénticos (consecutivos con mismo y) reteniendo
               extremos.
        """
        if len(scores) != len(labels):
            raise ValueError("scores and labels must have same length")
        if not scores:
            self.fitted = True
            return self

        # 1. order by score
        ordered = sorted(zip(scores, labels, strict=True), key=lambda p: p[0])

        # 2. PAV
        # Cada elemento del pool: (sum_y, weight, x_min, x_max)
        pools: list[list[float]] = []
        for x, y in ordered:
            pools.append([float(y), 1.0, float(x), float(x)])
            # mergear violations hacia atrás
            while len(pools) >= 2:
                a = pools[-2]
                b = pools[-1]
                ya = a[0] / a[1]
                yb = b[0] / b[1]
                if ya <= yb:
                    break
                merged = [
                    a[0] + b[0],
                    a[1] + b[1],
                    a[2],
                    b[3],
                ]
                pools.pop()
                pools.pop()
                pools.append(merged)

        # 3. extraer thresholds + calibrated
        thresholds: list[float] = []
        calibrated: list[float] = []
        for sum_y, weight, x_min, x_max in pools:
            y_mean = sum_y / weight
            # Anclar el pool en el centro del rango (mejor interpolación lineal)
            thresholds.append((x_min + x_max) / 2.0)
            calibrated.append(max(0.0, min(1.0, y_mean)))

        self.x_thresholds = thresholds
        self.y_calibrated = calibrated
        self.fitted = True
        return self

    # ------------------------------------------------------------------ #
    # Inference
    # ------------------------------------------------------------------ #
    def calibrate(self, score: float) -> float:
        """Interpolación lineal entre thresholds aprendidos."""
        if not self.fitted or not self.x_thresholds:
            return max(0.0, min(1.0, float(score)))

        xs = self.x_thresholds
        ys = self.y_calibrated

        if score <= xs[0]:
            return ys[0]
        if score >= xs[-1]:
            return ys[-1]

        # binary search
        lo = 0
        hi = len(xs) - 1
        while hi - lo > 1:
            mid = (lo + hi) // 2
            if xs[mid] <= score:
                lo = mid
            else:
                hi = mid

        x0, x1 = xs[lo], xs[hi]
        y0, y1 = ys[lo], ys[hi]
        if x1 == x0:
            return y0
        t = (score - x0) / (x1 - x0)
        return y0 + t * (y1 - y0)

    # ------------------------------------------------------------------ #
    # Persistence (no pickle — JSON-only)
    # ------------------------------------------------------------------ #
    def serialize(self) -> str:
        return json.dumps(
            {
                "version": self.version,
                "x_thresholds": self.x_thresholds,
                "y_calibrated": self.y_calibrated,
                "fitted": self.fitted,
            }
        )

    @classmethod
    def deserialize(cls, blob: str) -> IsotonicCalibrator:
        data: dict[str, Any] = json.loads(blob)
        c = cls(
            x_thresholds=list(data.get("x_thresholds", [])),
            y_calibrated=list(data.get("y_calibrated", [])),
            version=str(data.get("version", "v0")),
            fitted=bool(data.get("fitted", True)),
        )
        return c


# ---------------------------------------------------------------------- #
# Conformal Prediction / Venn-Abers (US-F15-03-03)
# ---------------------------------------------------------------------- #

try:
    import numpy as np  # type: ignore[import-untyped]

    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

try:
    from mapie.regression import MapieRegressor  # type: ignore[import-untyped]

    _MAPIE_AVAILABLE = True
except ImportError:
    _MAPIE_AVAILABLE = False


@dataclass(frozen=True)
class ConformalPrediction:
    """Resultado de una predicción conformal con intervalo y prioridad de revisión."""

    point_estimate: float
    lower_bound: float
    upper_bound: float
    review_priority: str | None


@dataclass
class ConformalWrapper:
    """Conformal prediction wrapper sobre IsotonicCalibrator.

    Garantiza cobertura empírica >= 1 - alpha en hold-out.

    Usa MAPIE si está instalado; en caso contrario usa Venn-Abers interno
    basado en residuales (|y_true - y_pred|) con quantile(1 - alpha).
    """

    calibrator: IsotonicCalibrator
    method: Literal["mapie", "venn_abers"] = "mapie"
    alpha: float = 0.02  # FP rate target: < 2%
    _fitted: bool = field(default=False, init=False)
    _residuals: list[float] = field(default_factory=list, init=False)
    _mapie: Any = field(default=None, init=False, repr=False)

    def fit(self, cal_scores: list[float], labels: list[int]) -> None:
        """Fit sobre hold-out (mínimo 200 muestras).

        Args:
            cal_scores: scores de calibración (crudos, en el rango del comparador).
            labels: etiquetas 0/1 (match real).

        Raises:
            ValueError: si len(cal_scores) < 200.
        """
        if len(cal_scores) < 200:
            raise ValueError(f"Insufficient calibration samples (min 200), got {len(cal_scores)}")
        if len(cal_scores) != len(labels):
            raise ValueError("cal_scores and labels must have same length")

        # Calcular predicciones calibradas del calibrador base
        y_pred = [self.calibrator.calibrate(s) for s in cal_scores]
        y_true = [float(lbl) for lbl in labels]

        if _MAPIE_AVAILABLE and self.method == "mapie":
            self._fit_mapie(cal_scores, y_true)
        else:
            # Venn-Abers interno: residuales absolutos
            self._residuals = [abs(yt - yp) for yt, yp in zip(y_true, y_pred, strict=True)]

        self._fitted = True

    def _fit_mapie(self, cal_scores: list[float], y_true: list[float]) -> None:
        """Ajusta MapieRegressor con cv='prefit' sobre el calibrador base."""
        import numpy as np

        # Wrapper sklearn-compatible que delega en IsotonicCalibrator
        from sklearn.base import (  # type: ignore[import-untyped]
            BaseEstimator,
            RegressorMixin,
        )

        class _CalWrapper(BaseEstimator, RegressorMixin):  # type: ignore[misc]
            def __init__(self, cal: IsotonicCalibrator) -> None:
                self.cal = cal

            def fit(self, X: Any, y: Any) -> _CalWrapper:
                return self

            def predict(self, X: Any) -> Any:
                return np.array([self.cal.calibrate(float(x[0])) for x in X])

        X_arr = np.array(cal_scores).reshape(-1, 1)
        y_arr = np.array(y_true)
        wrapped = _CalWrapper(self.calibrator)
        self._mapie = MapieRegressor(wrapped, cv="prefit", method="base")
        self._mapie.fit(X_arr, y_arr)

    def predict_with_interval(self, score: float) -> ConformalPrediction:
        """Retorna ConformalPrediction con point_estimate, lower_bound, upper_bound y review_priority.

        Args:
            score: score crudo a predecir.

        Returns:
            ConformalPrediction con todos los valores en [0.0, 1.0].
        """
        point_estimate = self.calibrator.calibrate(score)

        if _MAPIE_AVAILABLE and self.method == "mapie" and self._mapie is not None:
            lower, upper = self._predict_mapie(score, point_estimate)
        else:
            lower, upper = self._predict_venn_abers(point_estimate)

        # Calcular review_priority
        if lower > 0.70:
            review_priority: str | None = "low"
        elif upper < 0.50:
            review_priority = "high"
        else:
            review_priority = None

        return ConformalPrediction(
            point_estimate=point_estimate,
            lower_bound=lower,
            upper_bound=upper,
            review_priority=review_priority,
        )

    def _predict_mapie(self, score: float, point_estimate: float) -> tuple[float, float]:
        """Predice intervalo usando MAPIE."""
        import numpy as np

        X_arr = np.array([[score]])
        _, intervals = self._mapie.predict(X_arr, alpha=self.alpha)
        # intervals shape: (n_samples, 2, n_alphas)
        lower = float(intervals[0, 0, 0])
        upper = float(intervals[0, 1, 0])
        lower = max(0.0, min(1.0, lower))
        upper = max(0.0, min(1.0, upper))
        # Garantizar lower <= point <= upper
        lower = min(lower, point_estimate)
        upper = max(upper, point_estimate)
        return lower, upper

    def _predict_venn_abers(self, point_estimate: float) -> tuple[float, float]:
        """Predice intervalo con Venn-Abers interno (cuantil de residuales)."""
        if not self._residuals:
            return (point_estimate, point_estimate)

        if _NUMPY_AVAILABLE:
            import numpy as np

            margin = float(np.quantile(self._residuals, 1.0 - self.alpha))
        else:
            # Fallback puro Python si numpy no está disponible
            sorted_res = sorted(self._residuals)
            idx = int((1.0 - self.alpha) * len(sorted_res))
            idx = min(idx, len(sorted_res) - 1)
            margin = sorted_res[idx]

        lower = max(0.0, point_estimate - margin)
        upper = min(1.0, point_estimate + margin)
        return lower, upper


# ---------------------------------------------------------------------- #
# Métricas auxiliares (Brier score + ECE) — pure Python.
# ---------------------------------------------------------------------- #
def brier_score(predictions: list[float], labels: list[int]) -> float:
    """Brier score = mean((p-y)^2). Lower is better."""
    if not predictions:
        return 0.0
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must have same length")
    n = len(predictions)
    return sum((p - y) ** 2 for p, y in zip(predictions, labels, strict=True)) / n


def expected_calibration_error(
    predictions: list[float], labels: list[int], n_bins: int = 10
) -> float:
    """ECE — cuán lejos está la confianza promedio de la accuracy real por bin.

    Devuelve un valor en [0,1] (típicamente reportamos como porcentaje).
    """
    if not predictions:
        return 0.0
    if len(predictions) != len(labels):
        raise ValueError("predictions and labels must have same length")
    n = len(predictions)
    bins: list[list[tuple[float, int]]] = [[] for _ in range(n_bins)]
    for p, y in zip(predictions, labels, strict=True):
        idx = min(n_bins - 1, int(p * n_bins))
        bins[idx].append((p, y))
    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        avg_p = sum(p for p, _ in bucket) / len(bucket)
        avg_y = sum(y for _, y in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(avg_p - avg_y)
    return ece


__all__ = [
    "ConformalPrediction",
    "ConformalWrapper",
    "IsotonicCalibrator",
    "brier_score",
    "expected_calibration_error",
]
