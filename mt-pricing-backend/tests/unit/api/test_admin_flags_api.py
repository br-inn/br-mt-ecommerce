"""Unit tests del router `app.api.routes.admin_flags` (US-1A-09-08).

Patrón análogo a `test_graphrag_api`:
- FastAPI ad-hoc con el router montado en `/api/v1` (sin tocar app/main.py).
- Overrides en `get_db_session`, `get_current_user`, `require_permissions`,
  `get_flag_service`, `get_kill_switch`.
- Sin DB real — fakes in-memory.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.admin_flags import (
    get_flag_service,
    get_kill_switch,
)
from app.api.routes.admin_flags import (
    router as admin_flags_router,
)
from app.services.feature_flags.flag_service import (
    FLAG_KILL_SWITCH,
    FLAG_LIVE_NETWORK_AMAZON_UAE,
    KNOWN_FLAGS,
    FlagService,
)
from app.services.feature_flags.kill_switch import (
    KillSwitch,
    is_kill_switch_engaged,
    reset,
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


class _FakeFeatureFlagRow:
    def __init__(
        self,
        key: str,
        value: bool,
        updated_by: UUID | None = None,
    ) -> None:
        self.key = key
        self.value_jsonb = {"enabled": value}
        self.updated_by = updated_by
        now = datetime.now(tz=UTC)
        self.updated_at = now
        self.created_at = now


class _FakeRepo:
    def __init__(self) -> None:
        self.values: dict[str, bool] = {}
        self.rows: dict[str, _FakeFeatureFlagRow] = {}

    async def get_value(self, key: str) -> bool:
        return self.values.get(key, False)

    async def get(self, key: str) -> _FakeFeatureFlagRow | None:
        return self.rows.get(key)

    async def list_all(self) -> list[_FakeFeatureFlagRow]:
        return list(self.rows.values())

    async def upsert(
        self,
        *,
        key: str,
        value: bool,
        updated_by: UUID | None = None,
    ) -> _FakeFeatureFlagRow:
        self.values[key] = value
        row = _FakeFeatureFlagRow(key, value, updated_by)
        self.rows[key] = row
        return row


@pytest.fixture(autouse=True)
def _reset_kill_switch() -> None:
    reset()
    yield
    reset()


def _build_app(
    user: _FakeUser,
    repo: _FakeRepo,
) -> tuple[FastAPI, FlagService, KillSwitch]:
    app = FastAPI()
    app.include_router(admin_flags_router, prefix="/api/v1")

    fake_session = MagicMock()

    async def _override_db():  # pragma: no cover
        yield fake_session

    async def _override_user():
        return user

    svc = FlagService(flag_repo=repo, redis=None)
    ks = KillSwitch(svc)

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_flag_service] = lambda: svc
    app.dependency_overrides[get_kill_switch] = lambda: ks

    # Override `require_permissions(...)` closures
    for route in admin_flags_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):
                    return user

                app.dependency_overrides[call] = _allow

    return app, svc, ks


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_list_flags_returns_all_known_flags_even_when_db_empty() -> None:
    user = _FakeUser(perms=["flags:manage"])
    repo = _FakeRepo()
    app, _svc, _ks = _build_app(user, repo)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/admin/flags")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    keys = {f["key"] for f in body["flags"]}
    assert keys == set(KNOWN_FLAGS)
    # Todos a False (no había rows).
    assert all(f["enabled"] is False for f in body["flags"])


async def test_list_flags_includes_audit_columns() -> None:
    user = _FakeUser(perms=["flags:manage"])
    repo = _FakeRepo()
    repo.rows[FLAG_LIVE_NETWORK_AMAZON_UAE] = _FakeFeatureFlagRow(
        FLAG_LIVE_NETWORK_AMAZON_UAE, True, uuid4()
    )
    repo.values[FLAG_LIVE_NETWORK_AMAZON_UAE] = True

    app, _svc, _ks = _build_app(user, repo)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/admin/flags")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    item = next(
        (f for f in body["flags"] if f["key"] == FLAG_LIVE_NETWORK_AMAZON_UAE),
        None,
    )
    assert item is not None
    assert item["enabled"] is True
    assert item["updated_at"] is not None
    assert item["updated_by"] is not None


async def test_patch_flag_toggles_and_persists() -> None:
    user = _FakeUser(perms=["flags:manage"])
    repo = _FakeRepo()
    app, svc, _ks = _build_app(user, repo)
    async with await _client(app) as ac:
        resp = await ac.patch(
            f"/api/v1/admin/flags/{FLAG_LIVE_NETWORK_AMAZON_UAE}",
            json={"enabled": True},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["enabled"] is True
    assert body["key"] == FLAG_LIVE_NETWORK_AMAZON_UAE
    # Verifica que persistió.
    assert repo.values[FLAG_LIVE_NETWORK_AMAZON_UAE] is True


async def test_patch_unknown_flag_returns_404() -> None:
    user = _FakeUser(perms=["flags:manage"])
    repo = _FakeRepo()
    app, _svc, _ks = _build_app(user, repo)
    async with await _client(app) as ac:
        resp = await ac.patch(
            "/api/v1/admin/flags/UNKNOWN_FLAG_XYZ",
            json={"enabled": True},
        )
    assert resp.status_code == 404


async def test_kill_switch_engage_persists_and_engages_memory() -> None:
    user = _FakeUser(perms=["kill-switch:execute"])
    repo = _FakeRepo()
    app, _svc, _ks = _build_app(user, repo)
    assert is_kill_switch_engaged() is False
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/admin/flags/kill-switch",
            json={"engaged": True, "reason": "incident-005"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["engaged"] is True
    assert is_kill_switch_engaged() is True
    assert repo.values[FLAG_KILL_SWITCH] is True


async def test_kill_switch_disengage_clears_memory() -> None:
    user = _FakeUser(perms=["kill-switch:execute"])
    repo = _FakeRepo()
    app, _svc, _ks = _build_app(user, repo)
    async with await _client(app) as ac:
        await ac.post(
            "/api/v1/admin/flags/kill-switch",
            json={"engaged": True},
        )
        resp = await ac.post(
            "/api/v1/admin/flags/kill-switch",
            json={"engaged": False, "reason": "recovery"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["engaged"] is False
    assert is_kill_switch_engaged() is False


async def test_patch_flag_rejects_unknown_field_in_body() -> None:
    user = _FakeUser(perms=["flags:manage"])
    repo = _FakeRepo()
    app, _svc, _ks = _build_app(user, repo)
    async with await _client(app) as ac:
        resp = await ac.patch(
            f"/api/v1/admin/flags/{FLAG_LIVE_NETWORK_AMAZON_UAE}",
            json={"enabled": True, "extra_garbage": "x"},
        )
    assert resp.status_code == 422
