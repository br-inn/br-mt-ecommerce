"""Unit tests para GET /audit/prices/{price_id}/timeline (US-1B-02-09).

Estrategia:
- Monta FastAPI ad-hoc con SOLO el router de audit.
- Override de get_db_session, get_current_user y closures require_permissions.
- Stub de session.execute para devolver filas en-memoria.

Escenarios:
1. precio con eventos → devuelve lista ordenada ASC con payload_diff correcto.
2. precio sin eventos → devuelve lista vacía.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.audit import router as audit_router

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "gerente"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "gerente@mt.ae"
        self.full_name = "Gerente Test"
        self.is_active = True
        self.role = _FakeRole(["audit:read"])


class _FakeAuditEvent:
    """Objeto que mimetiza AuditEvent sólo con los campos que usa el endpoint."""

    def __init__(
        self,
        *,
        id: int,
        event_at: datetime,
        entity_type: str = "price",
        entity_id: str,
        action: str = "price.status_changed",
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        actor_role: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
        payload_diff: dict | None = None,
        reason: str | None = None,
        request_id: str | None = None,
        current_hash: str | None = None,
        prev_hash: str | None = None,
    ) -> None:
        self.id = id
        self.event_at = event_at
        self.entity_type = entity_type
        self.entity_id = entity_id
        self.action = action
        self.actor_id = actor_id
        self.actor_email = actor_email
        self.actor_role = actor_role
        self.before = before
        self.after = after
        self.payload_diff = payload_diff or {}
        self.reason = reason
        self.request_id = request_id
        self.current_hash = current_hash
        self.prev_hash = prev_hash


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------


def _fake_session_with_rows(rows: list[tuple[_FakeAuditEvent, _FakeUser | None]]) -> Any:
    """Crea un AsyncSession stub cuyo execute() devuelve las filas dadas."""
    mock_result = MagicMock()
    mock_result.all.return_value = rows
    session = MagicMock()
    session.execute = AsyncMock(return_value=mock_result)
    return session


def _build_app(session: Any) -> tuple[FastAPI, _FakeUser]:
    app = FastAPI()
    app.include_router(audit_router, prefix="/api/v1")

    user = _FakeUser()

    async def _override_db():  # pragma: no cover
        yield session

    async def _override_user() -> _FakeUser:
        return user

    def _override_perms_factory(*_codes: str):
        async def _ok() -> _FakeUser:
            return user

        return _ok

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    for route in app.routes:
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                if dep.call is None:
                    continue
                fn = dep.call
                if fn.__module__ == require_permissions.__module__ and fn.__qualname__.startswith(
                    "require_permissions."
                ):
                    app.dependency_overrides[fn] = _override_perms_factory()

    return app, user


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_price_timeline_returns_events_asc() -> None:
    """Escenario 1: precio con 2 eventos → lista en orden ASC con payload_diff."""
    price_id = uuid4()
    actor_id = uuid4()
    actor = _FakeUser()
    actor.id = actor_id

    t1 = datetime(2026, 5, 12, 10, 0, 0, tzinfo=timezone.utc)
    t2 = datetime(2026, 5, 12, 11, 0, 0, tzinfo=timezone.utc)

    evt1 = _FakeAuditEvent(
        id=1,
        event_at=t1,
        entity_id=str(price_id),
        action="price.status_changed",
        actor_id=actor_id,
        actor_email="gerente@mt.ae",
        payload_diff={"old_status": None, "new_status": "draft"},
    )
    evt2 = _FakeAuditEvent(
        id=2,
        event_at=t2,
        entity_id=str(price_id),
        action="price.status_changed",
        actor_id=actor_id,
        actor_email="gerente@mt.ae",
        payload_diff={"old_status": "draft", "new_status": "approved"},
    )

    rows: list[tuple[_FakeAuditEvent, _FakeUser | None]] = [
        (evt1, actor),
        (evt2, actor),
    ]
    session = _fake_session_with_rows(rows)
    app, _ = _build_app(session)

    async with await _client(app) as ac:
        resp = await ac.get(f"/api/v1/audit/prices/{price_id}/timeline")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 2

    # Orden ASC: primer evento es el más antiguo
    assert body[0]["payload_diff"]["old_status"] is None
    assert body[0]["payload_diff"]["new_status"] == "draft"
    assert body[1]["payload_diff"]["old_status"] == "draft"
    assert body[1]["payload_diff"]["new_status"] == "approved"

    # actor presente
    assert body[0]["actor"] is not None
    assert body[0]["actor"]["email"] == "gerente@mt.ae"

    # entity_type y entity_id correctos
    assert body[0]["entity_type"] == "price"
    assert body[0]["entity_id"] == str(price_id)


async def test_price_timeline_empty_when_no_events() -> None:
    """Escenario 2: precio sin eventos → lista vacía (200 OK)."""
    price_id = uuid4()
    session = _fake_session_with_rows([])
    app, _ = _build_app(session)

    async with await _client(app) as ac:
        resp = await ac.get(f"/api/v1/audit/prices/{price_id}/timeline")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body == []
