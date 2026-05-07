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
from typing import Any


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
    "IsotonicCalibrator",
    "brier_score",
    "expected_calibration_error",
]
