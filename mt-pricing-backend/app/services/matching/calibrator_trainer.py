"""Calibrator training pipeline — US-1A-09-07 (Sprint 5).

Orquesta:
1. Carga ``golden_labels`` recientes (default últimos 90 días).
2. Si ``len(labels) < min_samples`` → :class:`CalibratorTrainingNotReady`.
3. Entrena :class:`IsotonicCalibrator` con PAV (pure Python).
4. Calcula Brier + ECE pre/post para validar mejora (no-regression).
5. Persiste vía :class:`CalibratorStorage` con un version stamp.
6. NO promueve automáticamente — el operador decide via endpoint admin
   (POST /admin/calibrator/promote/{version}). Excepción: el task nightly
   puede ``auto_promote=True`` si el ECE mejoró ≥ 5%.

Decisiones (ADR-073):
- Pure Python (sin sklearn): el algoritmo PAV está en `calibrator.py`.
- JSON only (no pickle).
- Versionado opaco — version string `s5-YYYYMMDDHHMMSS-N` por default.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from uuid import UUID

from app.services.matching.calibrator import (
    IsotonicCalibrator,
    brier_score,
    expected_calibration_error,
)

if TYPE_CHECKING:
    from app.repositories.golden_labels import GoldenLabelRepository
    from app.services.matching.calibrator_storage import CalibratorStorage

logger = logging.getLogger(__name__)


# Mínimo de samples antes de entrenar (heurístico Sprint 5).
MIN_SAMPLES = 50
# Mejora mínima en ECE para auto-promover (5% relativo).
AUTO_PROMOTE_MIN_RELATIVE_IMPROVEMENT = 0.05


class CalibratorTrainingError(Exception):
    """Base para errores de la pipeline."""


class CalibratorTrainingNotReady(CalibratorTrainingError):
    """No hay suficientes golden labels para entrenar."""

    def __init__(self, found: int, required: int) -> None:
        super().__init__(f"insufficient golden labels: {found} found, {required} required")
        self.found = found
        self.required = required


@dataclass
class TrainingResult:
    """Output de :meth:`CalibratorTrainer.train`."""

    version: str
    trained_on_count: int
    brier_before: float
    brier_after: float
    ece_before: float
    ece_after: float
    auto_promoted: bool


class CalibratorTrainer:
    """Pipeline de entrenamiento — orquesta repo + storage + IsotonicCalibrator."""

    def __init__(
        self,
        *,
        golden_repo: GoldenLabelRepository,
        storage: CalibratorStorage,
        min_samples: int = MIN_SAMPLES,
    ) -> None:
        self.golden_repo = golden_repo
        self.storage = storage
        self.min_samples = min_samples

    async def train(
        self,
        *,
        since: datetime | None = None,
        version: str | None = None,
        trained_by: UUID | None = None,
        auto_promote: bool = False,
        clock: datetime | None = None,
    ) -> TrainingResult:
        """Entrena calibrator desde labels recientes y persiste.

        Args:
            since: cutoff de golden_labels.judged_at. Default = now - 90d.
            version: stamp opaco. Default ``s5-YYYYMMDDHHMMSS``.
            trained_by: user UUID que disparó el train (audit).
            auto_promote: si True y ECE mejora ≥ 5% relativo, promociona.
            clock: para inyectar tiempo en tests.
        """
        now = clock or datetime.now(tz=UTC)
        cutoff = since or (now - timedelta(days=90))

        labels = await self.golden_repo.list_for_training(since=cutoff)
        if len(labels) < self.min_samples:
            raise CalibratorTrainingNotReady(found=len(labels), required=self.min_samples)

        scores = [float(label_row.score) for label_row in labels]
        ys = [int(label_row.label) for label_row in labels]

        # Métricas pre-calibration (raw scores como predicciones).
        brier_before = brier_score(scores, ys)
        ece_before = expected_calibration_error(scores, ys, n_bins=10)

        cal = IsotonicCalibrator().fit(scores, ys)
        calibrated = [cal.calibrate(s) for s in scores]

        brier_after = brier_score(calibrated, ys)
        ece_after = expected_calibration_error(calibrated, ys, n_bins=10)

        ver = version or _default_version(now)
        await self.storage.save(
            cal,
            version=ver,
            trained_on_count=len(labels),
            brier_score=brier_after,
            ece=ece_after,
            trained_by=trained_by,
        )

        promoted = False
        if auto_promote:
            relative = _relative_improvement(ece_before, ece_after)
            if relative >= AUTO_PROMOTE_MIN_RELATIVE_IMPROVEMENT:
                await self.storage.promote(ver)
                promoted = True
                logger.info(
                    "calibrator.train.auto_promoted",
                    extra={
                        "version": ver,
                        "ece_before": ece_before,
                        "ece_after": ece_after,
                        "relative": relative,
                    },
                )
            else:
                logger.info(
                    "calibrator.train.no_auto_promote",
                    extra={
                        "version": ver,
                        "ece_before": ece_before,
                        "ece_after": ece_after,
                        "relative": relative,
                    },
                )

        return TrainingResult(
            version=ver,
            trained_on_count=len(labels),
            brier_before=brier_before,
            brier_after=brier_after,
            ece_before=ece_before,
            ece_after=ece_after,
            auto_promoted=promoted,
        )


def _default_version(when: datetime) -> str:
    return "s5-" + when.strftime("%Y%m%d%H%M%S")


def _relative_improvement(before: float, after: float) -> float:
    """Mejora relativa de ECE (lower-is-better → before-after / before)."""
    if before <= 0:
        return 0.0
    return max(0.0, (before - after) / before)


__all__ = [
    "AUTO_PROMOTE_MIN_RELATIVE_IMPROVEMENT",
    "CalibratorTrainer",
    "CalibratorTrainingError",
    "CalibratorTrainingNotReady",
    "MIN_SAMPLES",
    "TrainingResult",
]
