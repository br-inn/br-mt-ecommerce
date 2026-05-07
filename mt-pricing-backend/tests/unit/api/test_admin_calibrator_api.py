"""Unit tests del router `app.api.routes.admin_calibrator` (US-1A-09-07)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.admin_calibrator import (
    get_calibrator_storage,
    get_calibrator_trainer,
    router as admin_calibrator_router,
)
from app.services.matching.calibrator_trainer import (
    CalibratorTrainer,
    CalibratorTrainingNotReady,
    TrainingResult,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str]) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms)


class _FakeRow:
    def __init__(
        self,
        version: str,
        is_active: bool = True,
        trained_on_count: int = 75,
    ) -> None:
        self.version = version
        self.trained_on_count = trained_on_count
        self.brier_score = 0.05
        self.ece = 0.02
        self.is_active = is_active
        now = datetime.now(tz=UTC)
        self.trained_at = now
        self.promoted_at = now if is_active else None


class _FakeRepo:
    def __init__(self) -> None:
        self.active: _FakeRow | None = None
        self.versions: dict[str, _FakeRow] = {}

    async def get_active(self) -> _FakeRow | None:
        return self.active

    async def get_by_version(self, version: str) -> _FakeRow | None:
        return self.versions.get(version)

    async def store(self, **kw: Any) -> _FakeRow:
        row = _FakeRow(version=kw["version"], is_active=False)
        row.trained_on_count = kw["trained_on_count"]
        row.brier_score = kw.get("brier_score")
        row.ece = kw.get("ece")
        self.versions[kw["version"]] = row
        return row

    async def list_recent(self, limit: int = 20) -> list[_FakeRow]:
        return list(self.versions.values())[:limit]

    async def promote(
        self,
        version: str,
        *,
        promoted_at: datetime | None = None,
    ) -> _FakeRow:
        if version not in self.versions:
            raise ValueError("not found")
        for row in self.versions.values():
            row.is_active = False
        target = self.versions[version]
        target.is_active = True
        target.promoted_at = promoted_at
        self.active = target
        return target


class _FakeStorage:
    def __init__(self, repo: _FakeRepo) -> None:
        self.repo = repo

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
        await self.repo.store(
            version=version,
            model_json={},
            trained_on_count=trained_on_count,
            brier_score=brier_score,
            ece=ece,
            trained_by=trained_by,
        )
        return {"version": version, "is_active": False}

    async def load_active(self) -> Any:
        return None

    async def promote(self, version: str) -> dict[str, Any]:
        row = await self.repo.promote(version, promoted_at=datetime.now(tz=UTC))
        return {
            "version": row.version,
            "is_active": row.is_active,
            "promoted_at": row.promoted_at,
        }


class _FakeTrainer:
    def __init__(self, *, raise_not_ready: bool = False) -> None:
        self.raise_not_ready = raise_not_ready
        self.train_calls: list[dict[str, Any]] = []

    async def train(
        self,
        *,
        since: Any = None,
        version: str | None = None,
        trained_by: UUID | None = None,
        auto_promote: bool = False,
        clock: Any = None,
    ) -> TrainingResult:
        self.train_calls.append(
            {
                "since": since,
                "version": version,
                "trained_by": trained_by,
                "auto_promote": auto_promote,
            }
        )
        if self.raise_not_ready:
            raise CalibratorTrainingNotReady(found=10, required=50)
        return TrainingResult(
            version=version or "v-fake",
            trained_on_count=75,
            brier_before=0.2,
            brier_after=0.05,
            ece_before=0.15,
            ece_after=0.02,
            auto_promoted=auto_promote,
        )


def _build_app(
    user: _FakeUser,
    storage: _FakeStorage,
    trainer: _FakeTrainer,
) -> FastAPI:
    app = FastAPI()
    app.include_router(admin_calibrator_router, prefix="/api/v1")
    fake_session = MagicMock()

    async def _override_db():  # pragma: no cover
        yield fake_session

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_calibrator_storage] = lambda: storage
    app.dependency_overrides[get_calibrator_trainer] = lambda: trainer

    for route in admin_calibrator_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):  # noqa: ARG001
                    return user

                app.dependency_overrides[call] = _allow

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_get_active_returns_404_safe_response_when_no_active() -> None:
    user = _FakeUser(perms=["calibrator:train"])
    repo = _FakeRepo()
    storage = _FakeStorage(repo)
    trainer = _FakeTrainer()
    app = _build_app(user, storage, trainer)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/admin/calibrator/active")
    assert resp.status_code == 200
    body = resp.json()
    assert body["is_active"] is False
    assert body["version"] is None


async def test_get_active_returns_metadata() -> None:
    user = _FakeUser(perms=["calibrator:train"])
    repo = _FakeRepo()
    repo.active = _FakeRow(version="v-active", is_active=True)
    storage = _FakeStorage(repo)
    trainer = _FakeTrainer()
    app = _build_app(user, storage, trainer)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/admin/calibrator/active")
    assert resp.status_code == 200
    body = resp.json()
    assert body["version"] == "v-active"
    assert body["is_active"] is True
    assert body["trained_on_count"] == 75


async def test_train_endpoint_returns_metrics() -> None:
    user = _FakeUser(perms=["calibrator:train"])
    repo = _FakeRepo()
    storage = _FakeStorage(repo)
    trainer = _FakeTrainer()
    app = _build_app(user, storage, trainer)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/admin/calibrator/train",
            json={"auto_promote": False, "since_days": 30},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == "v-fake"
    assert body["brier_before"] == 0.2
    assert body["brier_after"] == 0.05
    assert body["ece_before"] == 0.15
    assert body["ece_after"] == 0.02
    assert body["auto_promoted"] is False

    call = trainer.train_calls[-1]
    assert call["auto_promote"] is False
    # since debe estar dentro del rango 30d (con tolerancia segundos).
    assert call["since"] is not None
    delta = datetime.now(tz=UTC) - call["since"]
    assert abs(delta - timedelta(days=30)) < timedelta(seconds=10)
    assert call["trained_by"] == user.id


async def test_train_endpoint_returns_409_when_not_ready() -> None:
    user = _FakeUser(perms=["calibrator:train"])
    repo = _FakeRepo()
    storage = _FakeStorage(repo)
    trainer = _FakeTrainer(raise_not_ready=True)
    app = _build_app(user, storage, trainer)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/admin/calibrator/train",
            json={"auto_promote": False},
        )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    assert body["detail"]["found"] == 10
    assert body["detail"]["required"] == 50


async def test_promote_endpoint_flips_active() -> None:
    user = _FakeUser(perms=["calibrator:train"])
    repo = _FakeRepo()
    repo.versions["v-target"] = _FakeRow(version="v-target", is_active=False)
    storage = _FakeStorage(repo)
    trainer = _FakeTrainer()
    app = _build_app(user, storage, trainer)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/admin/calibrator/promote/v-target")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["version"] == "v-target"
    assert body["is_active"] is True
    assert body["promoted_at"] is not None


async def test_promote_endpoint_404_when_version_unknown() -> None:
    user = _FakeUser(perms=["calibrator:train"])
    repo = _FakeRepo()
    storage = _FakeStorage(repo)
    trainer = _FakeTrainer()
    app = _build_app(user, storage, trainer)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/admin/calibrator/promote/v-missing")
    assert resp.status_code == 404


async def test_train_endpoint_default_payload_passes_no_since() -> None:
    user = _FakeUser(perms=["calibrator:train"])
    repo = _FakeRepo()
    storage = _FakeStorage(repo)
    trainer = _FakeTrainer()
    app = _build_app(user, storage, trainer)
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/admin/calibrator/train", json={})
    assert resp.status_code == 200, resp.text
    call = trainer.train_calls[-1]
    assert call["since"] is None
    assert call["auto_promote"] is False
