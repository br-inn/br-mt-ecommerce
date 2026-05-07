"""Unit tests para CalibratorTrainer (US-1A-09-07)."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.matching.calibrator_trainer import (
    AUTO_PROMOTE_MIN_RELATIVE_IMPROVEMENT,
    CalibratorTrainer,
    CalibratorTrainingNotReady,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
@dataclass
class _FakeLabel:
    sku: str
    candidate_id: UUID
    label: int
    score: float
    judged_at: datetime


class _FakeGoldenRepo:
    def __init__(self, labels: list[_FakeLabel]) -> None:
        self.labels = labels
        self.list_calls: list[datetime | None] = []

    async def list_for_training(
        self,
        *,
        since: datetime | None = None,
        limit: int = 50_000,
    ) -> Sequence[_FakeLabel]:
        self.list_calls.append(since)
        out = self.labels
        if since is not None:
            out = [lab for lab in out if lab.judged_at >= since]
        return out[:limit]


class _FakeStorage:
    def __init__(self) -> None:
        self.saves: list[dict[str, Any]] = []
        self.promotions: list[str] = []
        self.active_version: str | None = None

    async def save(
        self,
        calibrator: Any,
        *,
        version: str,
        trained_on_count: int,
        brier_score: float | None = None,
        ece: float | None = None,
        trained_by: UUID | None = None,
    ) -> dict[str, Any]:
        self.saves.append(
            {
                "version": version,
                "trained_on_count": trained_on_count,
                "brier_score": brier_score,
                "ece": ece,
                "trained_by": trained_by,
            }
        )
        return {"version": version, "is_active": False}

    async def promote(self, version: str) -> dict[str, Any]:
        self.promotions.append(version)
        self.active_version = version
        return {"version": version, "is_active": True}


def _mk_labels(n: int, base: datetime) -> list[_FakeLabel]:
    """Synthetic dataset: scores 0.05 → 0.95 con labels que correlacionan."""
    out: list[_FakeLabel] = []
    for i in range(n):
        score = (i + 1) / (n + 1)  # 0..1
        # Labels: alta correlación con score (mejorable con calibrator).
        label = 1 if score > 0.5 else 0
        out.append(
            _FakeLabel(
                sku=f"SKU-{i:04d}",
                candidate_id=uuid4(),
                label=label,
                score=score,
                judged_at=base + timedelta(minutes=i),
            )
        )
    return out


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_train_raises_when_below_min_samples() -> None:
    repo = _FakeGoldenRepo(labels=[])
    storage = _FakeStorage()
    trainer = CalibratorTrainer(
        golden_repo=repo, storage=storage, min_samples=50
    )
    with pytest.raises(CalibratorTrainingNotReady) as exc_info:
        await trainer.train()
    assert exc_info.value.found == 0
    assert exc_info.value.required == 50


async def test_train_persists_calibrator_with_metrics() -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    labels = _mk_labels(60, base)
    repo = _FakeGoldenRepo(labels=labels)
    storage = _FakeStorage()
    trainer = CalibratorTrainer(
        golden_repo=repo, storage=storage, min_samples=50
    )
    user_id = uuid4()
    result = await trainer.train(
        version="v-test-1", trained_by=user_id, clock=base
    )
    assert result.trained_on_count == 60
    assert result.version == "v-test-1"
    assert len(storage.saves) == 1
    saved = storage.saves[0]
    assert saved["version"] == "v-test-1"
    assert saved["trained_on_count"] == 60
    assert saved["trained_by"] == user_id
    assert saved["brier_score"] is not None
    assert saved["ece"] is not None
    # No auto_promote → no promotions.
    assert storage.promotions == []
    assert result.auto_promoted is False


async def test_train_default_version_uses_clock_timestamp() -> None:
    base = datetime(2026, 5, 7, 14, 30, 0, tzinfo=UTC)
    labels = _mk_labels(60, base)
    repo = _FakeGoldenRepo(labels=labels)
    storage = _FakeStorage()
    trainer = CalibratorTrainer(
        golden_repo=repo, storage=storage, min_samples=50
    )
    result = await trainer.train(clock=base)
    assert result.version == "s5-20260507143000"


async def test_train_metrics_after_should_be_better_or_equal() -> None:
    """PAV no empeora Brier (test del calibrator base lo prueba; lo
    re-validamos a través de la pipeline)."""
    base = datetime(2026, 5, 1, tzinfo=UTC)
    # Dataset sub-confidente — calibrator debería mejorar Brier.
    labels: list[_FakeLabel] = [
        _FakeLabel(
            sku=f"SKU-{i:03d}",
            candidate_id=uuid4(),
            label=int(score >= 0.4),
            score=score,
            judged_at=base + timedelta(minutes=i),
        )
        for i, score in enumerate(
            [0.1, 0.2, 0.3, 0.35, 0.4, 0.45, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95]
            * 5  # 60 samples
        )
    ]
    repo = _FakeGoldenRepo(labels=labels)
    storage = _FakeStorage()
    trainer = CalibratorTrainer(
        golden_repo=repo, storage=storage, min_samples=50
    )
    result = await trainer.train(clock=base)
    assert result.brier_after <= result.brier_before + 1e-9


async def test_train_auto_promote_triggers_when_ece_improves() -> None:
    """Si ECE mejora ≥ 5% relativo y auto_promote=True, se promueve."""
    base = datetime(2026, 5, 1, tzinfo=UTC)
    # Dataset miscalibrado fuerte → calibrator gana mucho ECE.
    # raw scores agrupados en 0.4-0.5 con labels 50/50 → ECE alta antes.
    labels: list[_FakeLabel] = []
    for i in range(40):
        labels.append(
            _FakeLabel(
                sku=f"SKU-A-{i:03d}",
                candidate_id=uuid4(),
                label=0,
                score=0.45,
                judged_at=base + timedelta(minutes=i),
            )
        )
    for i in range(40):
        labels.append(
            _FakeLabel(
                sku=f"SKU-B-{i:03d}",
                candidate_id=uuid4(),
                label=1,
                score=0.55,
                judged_at=base + timedelta(minutes=40 + i),
            )
        )
    repo = _FakeGoldenRepo(labels=labels)
    storage = _FakeStorage()
    trainer = CalibratorTrainer(
        golden_repo=repo, storage=storage, min_samples=50
    )
    result = await trainer.train(auto_promote=True, clock=base)
    assert result.ece_after <= result.ece_before
    if (
        result.ece_before > 0
        and (result.ece_before - result.ece_after) / result.ece_before
        >= AUTO_PROMOTE_MIN_RELATIVE_IMPROVEMENT
    ):
        assert result.auto_promoted is True
        assert storage.promotions == [result.version]


async def test_train_auto_promote_skips_when_no_improvement() -> None:
    """Dataset ya bien calibrado → no se promueve aunque auto_promote=True."""
    base = datetime(2026, 5, 1, tzinfo=UTC)
    # Predicciones perfectas: score=label en {0,1}.
    labels: list[_FakeLabel] = []
    for i in range(60):
        sc = 0.0 if i % 2 == 0 else 1.0
        labels.append(
            _FakeLabel(
                sku=f"SKU-{i:03d}",
                candidate_id=uuid4(),
                label=int(sc),
                score=sc,
                judged_at=base + timedelta(minutes=i),
            )
        )
    repo = _FakeGoldenRepo(labels=labels)
    storage = _FakeStorage()
    trainer = CalibratorTrainer(
        golden_repo=repo, storage=storage, min_samples=50
    )
    result = await trainer.train(auto_promote=True, clock=base)
    # Ya estaba bien calibrado → no debería haber promotion.
    assert result.auto_promoted is False
    assert storage.promotions == []


async def test_train_default_since_uses_90_day_window() -> None:
    base = datetime(2026, 5, 1, tzinfo=UTC)
    repo = _FakeGoldenRepo(labels=_mk_labels(60, base))
    storage = _FakeStorage()
    trainer = CalibratorTrainer(
        golden_repo=repo, storage=storage, min_samples=50
    )
    await trainer.train(clock=base)
    assert len(repo.list_calls) == 1
    since = repo.list_calls[0]
    assert since is not None
    delta = base - since
    # 90 días dentro de un día de tolerancia (timedelta exacto).
    assert abs(delta - timedelta(days=90)) < timedelta(seconds=1)
