"""Tasks para la queue ``comparator`` — calibrator nightly retrain (US-1A-09-07).

Patrón:
- ``mt.calibrator.retrain_nightly`` corre 02:00 Asia/Dubai cada noche cuando
  el job_definition se cree (Sprint 5+). Por ahora invocable manual o desde
  ``apply()`` en tests.
- Construye un AsyncSession propio (las tasks Celery no comparten request scope
  de FastAPI) y delega en :class:`CalibratorTrainer`.
- ``auto_promote=True`` por defecto en nightly: si la nueva versión mejora
  el ECE ≥ 5% relativo, se promueve sin intervención humana. Si no, queda
  parked esperando que un operador valide manualmente.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


async def _run_retrain(auto_promote: bool, since_days: int | None) -> dict[str, Any]:
    """Helper async — abre session, dispara train, commit."""
    from datetime import UTC, datetime, timedelta

    from app.db import get_sessionmaker
    from app.repositories.golden_labels import (
        CalibratorVersionRepository,
        GoldenLabelRepository,
    )
    from app.services.matching.calibrator_storage import CalibratorStorage
    from app.services.matching.calibrator_trainer import (
        CalibratorTrainer,
        CalibratorTrainingNotReady,
    )

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        async with session.begin():
            golden_repo = GoldenLabelRepository(session)
            calibrator_repo = CalibratorVersionRepository(session)
            storage = CalibratorStorage(calibrator_repo)
            trainer = CalibratorTrainer(golden_repo=golden_repo, storage=storage)

            since = None
            if since_days is not None:
                since = datetime.now(tz=UTC) - timedelta(days=since_days)

            try:
                result = await trainer.train(
                    since=since,
                    auto_promote=auto_promote,
                )
            except CalibratorTrainingNotReady as exc:
                return {
                    "skipped": True,
                    "reason": "not_ready",
                    "found": exc.found,
                    "required": exc.required,
                }
        return {
            "skipped": False,
            "version": result.version,
            "trained_on_count": result.trained_on_count,
            "brier_before": result.brier_before,
            "brier_after": result.brier_after,
            "ece_before": result.ece_before,
            "ece_after": result.ece_after,
            "auto_promoted": result.auto_promoted,
        }


@celery_app.task(
    name="mt.calibrator.retrain_nightly",
    bind=True,
    acks_late=True,
)
def retrain_nightly(  # noqa: ANN001
    self,
    auto_promote: bool = True,
    since_days: int | None = 90,
) -> dict[str, Any]:
    """Entrena IsotonicCalibrator desde golden_labels recientes.

    Llamada desde job_definition `calibrator_retrain_nightly` (cron 02:00
    Asia/Dubai daily, when seeded — TODO Sprint 5+).
    """
    try:
        result = asyncio.run(_run_retrain(auto_promote=auto_promote, since_days=since_days))
    except Exception as exc:  # noqa: BLE001
        logger.exception("calibrator.retrain.failed", extra={"error": str(exc)})
        raise
    logger.info("calibrator.retrain.done", extra=result)
    return result


@celery_app.task(name="mt.calibrator.health_ping")
def health_ping() -> str:
    return "ok"


__all__ = ["health_ping", "retrain_nightly"]
