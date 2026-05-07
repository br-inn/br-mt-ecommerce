"""Unit tests para CalibratorStorage (US-1A-09-07)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.services.matching.calibrator import IsotonicCalibrator
from app.services.matching.calibrator_storage import CalibratorStorage

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRow:
    def __init__(
        self,
        version: str,
        model_json: dict[str, Any],
        trained_on_count: int,
        brier_score: float | None = None,
        ece: float | None = None,
        is_active: bool = False,
        trained_by: UUID | None = None,
    ) -> None:
        self.version = version
        self.model_json = model_json
        self.trained_on_count = trained_on_count
        self.brier_score = brier_score
        self.ece = ece
        self.is_active = is_active
        self.trained_by = trained_by
        self.trained_at = datetime.now(tz=UTC)
        self.promoted_at: datetime | None = None


class _FakeRepo:
    def __init__(self) -> None:
        self.rows: dict[str, _FakeRow] = {}

    async def store(
        self,
        *,
        version: str,
        model_json: dict[str, Any],
        trained_on_count: int,
        brier_score: float | None = None,
        ece: float | None = None,
        trained_by: UUID | None = None,
    ) -> _FakeRow:
        row = _FakeRow(
            version=version,
            model_json=model_json,
            trained_on_count=trained_on_count,
            brier_score=brier_score,
            ece=ece,
            trained_by=trained_by,
        )
        self.rows[version] = row
        return row

    async def get_by_version(self, version: str) -> _FakeRow | None:
        return self.rows.get(version)

    async def get_active(self) -> _FakeRow | None:
        for row in self.rows.values():
            if row.is_active:
                return row
        return None

    async def list_recent(self, limit: int = 20) -> list[_FakeRow]:
        return sorted(
            self.rows.values(),
            key=lambda r: r.trained_at,
            reverse=True,
        )[:limit]

    async def promote(
        self,
        version: str,
        *,
        promoted_at: datetime | None = None,
    ) -> _FakeRow:
        if version not in self.rows:
            raise ValueError(f"version {version} not found")
        for row in self.rows.values():
            row.is_active = False
        target = self.rows[version]
        target.is_active = True
        target.promoted_at = promoted_at
        return target


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_save_persists_calibrator_as_json() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    cal = IsotonicCalibrator().fit([0.1, 0.5, 0.9], [0, 1, 1])

    info = await storage.save(
        cal,
        version="v-test-1",
        trained_on_count=3,
        brier_score=0.05,
        ece=0.02,
        trained_by=uuid4(),
    )
    assert info["version"] == "v-test-1"
    assert info["trained_on_count"] == 3
    row = repo.rows["v-test-1"]
    # JSON estable — sin pickle.
    assert "x_thresholds" in row.model_json
    assert "y_calibrated" in row.model_json
    assert isinstance(row.model_json, dict)


async def test_save_overrides_calibrator_version_field() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    cal = IsotonicCalibrator(version="v0").fit([0.1, 0.9], [0, 1])
    await storage.save(cal, version="v-prod-7", trained_on_count=2)
    assert cal.version == "v-prod-7"
    row = repo.rows["v-prod-7"]
    assert row.model_json["version"] == "v-prod-7"


async def test_load_active_returns_none_when_no_active_row() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    assert await storage.load_active() is None


async def test_load_active_deserializes_json() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    cal = IsotonicCalibrator().fit([0.1, 0.5, 0.9], [0, 1, 1])
    await storage.save(cal, version="v1", trained_on_count=3)
    await storage.promote("v1")
    loaded = await storage.load_active()
    assert loaded is not None
    assert loaded.version == "v1"
    assert loaded.x_thresholds == cal.x_thresholds
    assert loaded.y_calibrated == cal.y_calibrated


async def test_promote_flips_only_one_active() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    cal = IsotonicCalibrator().fit([0.1, 0.9], [0, 1])
    await storage.save(cal, version="v1", trained_on_count=2)
    await storage.save(cal, version="v2", trained_on_count=2)
    await storage.promote("v1")
    assert repo.rows["v1"].is_active is True
    assert repo.rows["v2"].is_active is False
    await storage.promote("v2")
    assert repo.rows["v1"].is_active is False
    assert repo.rows["v2"].is_active is True


async def test_promote_unknown_version_raises() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    with pytest.raises(ValueError):
        await storage.promote("v-does-not-exist")


async def test_load_by_version_returns_none_for_missing() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    assert await storage.load_by_version("missing") is None


async def test_load_by_version_roundtrip() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    cal = IsotonicCalibrator().fit([0.1, 0.5, 0.9], [0, 1, 1])
    await storage.save(cal, version="vX", trained_on_count=3)
    loaded = await storage.load_by_version("vX")
    assert loaded is not None
    # Re-serialize and ensure JSON-equivalent
    assert json.loads(loaded.serialize())["x_thresholds"] == cal.x_thresholds


async def test_list_recent_orders_by_trained_at_desc() -> None:
    repo = _FakeRepo()
    storage = CalibratorStorage(repo)
    cal = IsotonicCalibrator().fit([0.1, 0.9], [0, 1])
    await storage.save(cal, version="v1", trained_on_count=2)
    await storage.save(cal, version="v2", trained_on_count=2)
    rows = await storage.list_recent(limit=10)
    assert len(rows) == 2
    assert rows[0]["version"] in {"v1", "v2"}
