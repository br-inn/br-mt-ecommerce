"""Unit tests para mt.calibrator.retrain_nightly Celery task (US-1A-09-07)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.matching.calibrator_trainer import (
    CalibratorTrainingNotReady,
    TrainingResult,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_training_result(auto_promoted: bool = True) -> TrainingResult:
    return TrainingResult(
        version="s5-test",
        trained_on_count=75,
        brier_before=0.2,
        brier_after=0.05,
        ece_before=0.15,
        ece_after=0.03,
        auto_promoted=auto_promoted,
    )


# ---------------------------------------------------------------------------
# _run_retrain helper
# ---------------------------------------------------------------------------
async def test_run_retrain_returns_metrics_on_success() -> None:
    from app.workers.tasks.calibrator import _run_retrain

    fake_session = MagicMock()
    fake_session.begin = MagicMock()
    fake_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
    fake_session.begin.return_value.__aexit__ = AsyncMock(return_value=None)

    class _SessionFactory:
        def __call__(self) -> Any:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=fake_session)
            ctx.__aexit__ = AsyncMock(return_value=None)
            return ctx

    fake_trainer = MagicMock()
    fake_trainer.train = AsyncMock(return_value=_make_training_result(auto_promoted=True))

    with (
        patch(
            "app.db.get_sessionmaker",
            return_value=_SessionFactory(),
        ),
        patch(
            "app.workers.tasks.calibrator.GoldenLabelRepository"
            if False
            else "app.repositories.golden_labels.GoldenLabelRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.repositories.golden_labels.CalibratorVersionRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.matching.calibrator_storage.CalibratorStorage",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.matching.calibrator_trainer.CalibratorTrainer",
            return_value=fake_trainer,
        ),
    ):
        out = await _run_retrain(auto_promote=True, since_days=90)

    assert out["skipped"] is False
    assert out["version"] == "s5-test"
    assert out["trained_on_count"] == 75
    assert out["auto_promoted"] is True


async def test_run_retrain_returns_skipped_when_not_ready() -> None:
    from app.workers.tasks.calibrator import _run_retrain

    fake_session = MagicMock()

    class _SessionFactory:
        def __call__(self) -> Any:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=fake_session)
            ctx.__aexit__ = AsyncMock(return_value=None)
            fake_session.begin = MagicMock()
            fake_session.begin.return_value.__aenter__ = AsyncMock(return_value=None)
            fake_session.begin.return_value.__aexit__ = AsyncMock(return_value=None)
            return ctx

    fake_trainer = MagicMock()
    fake_trainer.train = AsyncMock(side_effect=CalibratorTrainingNotReady(found=10, required=50))

    with (
        patch(
            "app.db.get_sessionmaker",
            return_value=_SessionFactory(),
        ),
        patch(
            "app.repositories.golden_labels.GoldenLabelRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.repositories.golden_labels.CalibratorVersionRepository",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.matching.calibrator_storage.CalibratorStorage",
            return_value=MagicMock(),
        ),
        patch(
            "app.services.matching.calibrator_trainer.CalibratorTrainer",
            return_value=fake_trainer,
        ),
    ):
        out = await _run_retrain(auto_promote=True, since_days=90)

    assert out["skipped"] is True
    assert out["reason"] == "not_ready"
    assert out["found"] == 10
    assert out["required"] == 50


# ---------------------------------------------------------------------------
# Celery task wrapper
# ---------------------------------------------------------------------------
def test_retrain_nightly_task_is_registered() -> None:
    from app.workers.worker import celery_app

    assert "mt.calibrator.retrain_nightly" in celery_app.tasks
    assert "mt.calibrator.health_ping" in celery_app.tasks


def test_retrain_nightly_default_kwargs_are_safe() -> None:
    """auto_promote=True + since_days=90 son los valores documentados."""
    import inspect

    from app.workers.tasks.calibrator import retrain_nightly

    # bind=True hace que self sea primer arg → inspeccionamos el wrapper.
    fn = retrain_nightly.run  # underlying callable
    sig = inspect.signature(fn)
    params = sig.parameters
    assert params["auto_promote"].default is True
    assert params["since_days"].default == 90


def test_retrain_nightly_task_propagates_exceptions() -> None:
    from app.workers.tasks import calibrator as task_mod

    with patch.object(
        task_mod,
        "_run_retrain",
        side_effect=RuntimeError("boom"),
    ):
        with pytest.raises(RuntimeError, match="boom"):
            # Evitamos asyncio.run cubierto por _run_retrain — el patch lo
            # reemplaza ya. La task wrapper hace asyncio.run() sobre la
            # corutina; con _run_retrain síncronamente fallando, asyncio.run
            # propaga el RuntimeError.
            task_mod.retrain_nightly.run(  # type: ignore[attr-defined]
                auto_promote=False, since_days=30
            )


def test_retrain_nightly_task_returns_dict_on_success() -> None:
    from app.workers.tasks import calibrator as task_mod

    async def _ok(auto_promote: bool, since_days: int | None) -> dict[str, Any]:
        return {
            "skipped": False,
            "version": "v-ok",
            "trained_on_count": 75,
            "brier_before": 0.2,
            "brier_after": 0.05,
            "ece_before": 0.15,
            "ece_after": 0.03,
            "auto_promoted": True,
        }

    with patch.object(task_mod, "_run_retrain", side_effect=_ok):
        result = task_mod.retrain_nightly.run(  # type: ignore[attr-defined]
            auto_promote=True, since_days=90
        )
    assert result["version"] == "v-ok"
    assert result["auto_promoted"] is True
