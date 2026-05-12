"""Unit tests del router `app.api.routes.dr_drills` (US-DR-DRILLS).

Estrategia:
- FastAPI ad-hoc montada con el router bajo `/api/v1`.
- Override de `get_db_session`, `get_current_user` y `require_permissions`
  con fakes in-memory (sin DB real ni JWT real).

Cobertura:
1. ``POST /dr-drills`` crea drill, retorna 201 con id.
2. ``GET /dr-drills`` retorna [] cuando la BD está vacía.
3. ``GET /dr-drills/summary`` retorna counts en 0 cuando vacío.
"""

from __future__ import annotations

from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.dr_drills import router as dr_drills_router

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self) -> None:
        self.code = "admin"
        self.permissions_snapshot = ["admin"]


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "admin@mt.ae"
        self.is_active = True
        self.deleted_at = None
        self.role = _FakeRole()


class _FakeScalarResult:
    def __init__(self, items: list[Any]) -> None:
        self._items = items

    def all(self) -> list[Any]:
        return self._items

    def scalar_one(self) -> Any:
        return self._items[0] if self._items else 0

    def scalar_one_or_none(self) -> Any | None:
        return self._items[0] if self._items else None

    def __iter__(self):
        return iter(self._items)


class _FakeExecuteResult:
    def __init__(self, items: list[Any], scalar_val: Any = None) -> None:
        self._items = items
        self._scalar = scalar_val

    def scalars(self) -> _FakeScalarResult:
        return _FakeScalarResult(self._items)

    def scalar_one(self) -> Any:
        return self._scalar if self._scalar is not None else (self._items[0] if self._items else 0)

    def scalar_one_or_none(self) -> Any | None:
        return self._items[0] if self._items else None

    def __iter__(self):
        return iter(self._items)


class _FakeDrillRow:
    def __init__(self, **kw: Any) -> None:
        self.id: UUID = kw.get("id", uuid4())
        self.drill_type: str = kw.get("drill_type", "full_failover")
        self.scheduled_date: date = kw.get("scheduled_date", date(2026, 6, 1))
        self.executed_date: date | None = kw.get("executed_date")
        self.outcome: str | None = kw.get("outcome")
        self.duration_minutes: int | None = kw.get("duration_minutes")
        self.findings: str | None = kw.get("findings")
        self.runbook_ref: str | None = kw.get("runbook_ref")
        self.conducted_by_user_id: UUID | None = kw.get("conducted_by_user_id")
        self.notes: str | None = kw.get("notes")


# ---------------------------------------------------------------------------
# App builder helpers
# ---------------------------------------------------------------------------
def _build_app(session_mock: Any, user: _FakeUser) -> FastAPI:
    app = FastAPI()
    app.include_router(dr_drills_router, prefix="/api/v1")

    async def _override_db():
        yield session_mock

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    for route in dr_drills_router.routes:
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


async def _make_client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_create_drill_success() -> None:
    """POST /dr-drills crea drill y retorna 201 con id."""
    user = _FakeUser()
    created_drill = _FakeDrillRow(
        id=uuid4(),
        drill_type="db_restore",
        scheduled_date=date(2026, 7, 1),
    )

    session = MagicMock()
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock(side_effect=lambda obj: None)

    session.get = AsyncMock(return_value=None)

    session.execute = AsyncMock(return_value=_FakeExecuteResult([created_drill]))

    async def _fake_refresh(obj: Any) -> None:
        obj.id = created_drill.id
        obj.drill_type = created_drill.drill_type
        obj.scheduled_date = created_drill.scheduled_date
        obj.executed_date = None
        obj.outcome = None
        obj.duration_minutes = None
        obj.findings = None
        obj.runbook_ref = None
        obj.conducted_by_user_id = None
        obj.notes = None

    session.refresh = AsyncMock(side_effect=_fake_refresh)

    app = _build_app(session, user)

    async with await _make_client(app) as ac:
        resp = await ac.post(
            "/api/v1/dr-drills",
            json={"drill_type": "db_restore", "scheduled_date": "2026-07-01"},
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "id" in body
    assert body["drill_type"] == "db_restore"


async def test_list_drills_empty() -> None:
    """GET /dr-drills devuelve [] cuando no hay drills."""
    user = _FakeUser()

    session = MagicMock()
    session.execute = AsyncMock(return_value=_FakeExecuteResult([]))

    app = _build_app(session, user)

    async with await _make_client(app) as ac:
        resp = await ac.get("/api/v1/dr-drills")

    assert resp.status_code == 200, resp.text
    assert resp.json() == []


async def test_get_summary_empty() -> None:
    """GET /dr-drills/summary retorna counts en 0 cuando no hay drills."""
    user = _FakeUser()

    call_count = 0

    async def _fake_execute(stmt: Any) -> _FakeExecuteResult:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return _FakeExecuteResult([], scalar_val=0)
        return _FakeExecuteResult([])

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_fake_execute)

    app = _build_app(session, user)

    async with await _make_client(app) as ac:
        resp = await ac.get("/api/v1/dr-drills/summary")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["total"] == 0
    assert body["by_outcome"] == {}
    assert body["last_drill_date"] is None
    assert body["next_scheduled_date"] is None
    assert body["drills_by_runbook"] == {}
