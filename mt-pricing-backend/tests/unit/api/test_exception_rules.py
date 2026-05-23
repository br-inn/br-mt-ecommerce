"""Unit tests para `app.api.routes.exception_rules` — US-1B-02-02.

Cobertura (6 tests):
1. crear regla exitoso → 201
2. activar regla cierra la anterior activa del mismo scope
3. RLS: gerente (prices:approve) puede crear
4. RLS: ti_integracion sin prices:approve → 403 al crear
5. historial ordenado created_at desc
6. activar regla inexistente → 404
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.exception_rules import router as er_router

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeRole:
    def __init__(self, code: str, perms: list[str]) -> None:
        self.code = code
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, role_code: str = "gerente", perms: list[str] | None = None) -> None:
        self.id: UUID = uuid4()
        self.email = f"{role_code}@mt.ae"
        self.is_active = True
        self.deleted_at = None
        self.role = _FakeRole(
            role_code,
            perms if perms is not None else ["prices:approve", "prices:read"],
        )


def _make_rule(
    *,
    code: str = "default_rule",
    active: bool = False,
    channel_id: UUID | None = None,
    scheme_code: str | None = None,
    created_offset_hours: int = 0,
) -> Any:
    now = datetime.now(tz=UTC) - timedelta(hours=created_offset_hours)
    return SimpleNamespace(
        id=uuid4(),
        code=code,
        description=None,
        channel_id=channel_id,
        scheme_code=scheme_code,
        margin_threshold_pct=Decimal("5.0"),
        fx_swing_threshold_pct=Decimal("3.0"),
        min_margin_pct=Decimal("8.0"),
        active=active,
        version=1,
        effective_from=now,
        effective_to=None,
        created_by=None,
        created_at=now,
        updated_at=now,
    )


class _FakeRepo:
    """Stub de ExceptionRuleRepository — puro in-memory."""

    def __init__(self) -> None:
        self._rules: dict[UUID, Any] = {}
        self._by_code: dict[str, Any] = {}
        self.activated: list[UUID] = []

    def seed(self, rule: Any) -> None:
        self._rules[rule.id] = rule
        self._by_code[rule.code] = rule

    async def get_by_code(self, code: str) -> Any | None:
        return self._by_code.get(code)

    async def create(self, data: dict) -> Any:  # type: ignore[override]
        rule = _make_rule(
            code=data["code"],
            active=data.get("active", False),
            channel_id=data.get("channel_id"),
            scheme_code=data.get("scheme_code"),
        )
        rule.description = data.get("description")
        rule.created_by = data.get("created_by")
        self.seed(rule)
        return rule

    async def get_by_id(self, rule_id: UUID) -> Any | None:
        return self._rules.get(rule_id)

    async def activate(self, rule_id: UUID, actor_id: UUID) -> Any:
        rule = self._rules.get(rule_id)
        if rule is None:
            raise ValueError(f"ExceptionRule {rule_id} not found")
        for r in list(self._rules.values()):
            if (
                r.active
                and r.channel_id == rule.channel_id
                and r.scheme_code == rule.scheme_code
                and r.id != rule_id
            ):
                r.active = False
                r.effective_to = datetime.now(tz=UTC)
        rule.active = True
        rule.effective_from = datetime.now(tz=UTC)
        rule.effective_to = None
        self.activated.append(rule_id)
        return rule

    async def list_history(self, *, limit: int = 50) -> list[Any]:
        rules = sorted(self._rules.values(), key=lambda r: r.created_at, reverse=True)
        return rules[:limit]


class _FakeAuditRepo:
    def __init__(self) -> None:
        self.records: list[dict] = []

    async def record(self, **kwargs: Any) -> None:
        self.records.append(kwargs)


# ---------------------------------------------------------------------------
# App factory — overrides deps + monkeypatches repo constructors
# ---------------------------------------------------------------------------


def _make_app(
    user: _FakeUser,
    repo: _FakeRepo,
    audit: _FakeAuditRepo,
) -> FastAPI:
    app = FastAPI()
    app.include_router(er_router)

    # Fake session (never used — repos are monkeypatched)
    fake_session = MagicMock()

    async def _fake_session():  # type: ignore[return]
        yield fake_session

    app.dependency_overrides[get_db_session] = _fake_session
    app.dependency_overrides[get_current_user] = lambda: user

    # require_permissions factory → checks perms against fake user
    def _perms_factory(*required: str):
        def _check():
            snapshot = set(user.role.permissions_snapshot or [])
            missing = set(required) - snapshot
            if missing:
                from fastapi import HTTPException

                raise HTTPException(
                    status_code=403,
                    detail={"code": "permission_denied", "missing": sorted(missing)},
                )
            return user

        return _check

    app.dependency_overrides[require_permissions] = _perms_factory  # type: ignore[assignment]

    return app


# ---------------------------------------------------------------------------
# Test 1: crear regla exitoso → 201
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_create_rule_success() -> None:
    user = _FakeUser("gerente")
    repo = _FakeRepo()
    audit = _FakeAuditRepo()
    app = _make_app(user, repo, audit)

    with (
        patch("app.api.routes.exception_rules.ExceptionRuleRepository", return_value=repo),
        patch("app.api.routes.exception_rules.AuditRepository", return_value=audit),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/exception-rules",
                json={
                    "code": "test_rule_01",
                    "description": "Regla de prueba",
                    "margin_threshold_pct": "5.00",
                    "fx_swing_threshold_pct": "3.00",
                    "min_margin_pct": "8.00",
                },
            )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["code"] == "test_rule_01"
    assert body["active"] is False  # creada inactiva
    assert len(audit.records) == 1
    assert audit.records[0]["action"] == "exception_rule.created"


# ---------------------------------------------------------------------------
# Test 2: activar regla cierra la anterior activa del mismo scope
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_activate_closes_previous() -> None:
    user = _FakeUser("gerente")
    repo = _FakeRepo()
    audit = _FakeAuditRepo()

    old_rule = _make_rule(code="old_rule", active=True)
    new_rule = _make_rule(code="new_rule", active=False)
    repo.seed(old_rule)
    repo.seed(new_rule)

    app = _make_app(user, repo, audit)

    with (
        patch("app.api.routes.exception_rules.ExceptionRuleRepository", return_value=repo),
        patch("app.api.routes.exception_rules.AuditRepository", return_value=audit),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(f"/exception-rules/{new_rule.id}/activate")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["active"] is True

    # Anterior debe estar cerrada.
    assert old_rule.active is False
    assert old_rule.effective_to is not None
    assert new_rule.id in repo.activated


# ---------------------------------------------------------------------------
# Test 3: gerente con prices:approve puede crear
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_gerente_can_create() -> None:
    user = _FakeUser("gerente", perms=["prices:approve", "prices:read"])
    repo = _FakeRepo()
    audit = _FakeAuditRepo()
    app = _make_app(user, repo, audit)

    with (
        patch("app.api.routes.exception_rules.ExceptionRuleRepository", return_value=repo),
        patch("app.api.routes.exception_rules.AuditRepository", return_value=audit),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/exception-rules",
                json={"code": "gerente_rule"},
            )

    assert resp.status_code == 201, resp.text


# ---------------------------------------------------------------------------
# Test 4: ti_integracion sin prices:approve → 403 al crear
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_ti_sin_approve_cannot_create() -> None:
    user = _FakeUser("ti_integracion", perms=["prices:read"])  # sin prices:approve
    repo = _FakeRepo()
    audit = _FakeAuditRepo()
    app = _make_app(user, repo, audit)

    with (
        patch("app.api.routes.exception_rules.ExceptionRuleRepository", return_value=repo),
        patch("app.api.routes.exception_rules.AuditRepository", return_value=audit),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.post(
                "/exception-rules",
                json={"code": "blocked_rule"},
            )

    assert resp.status_code == 403, resp.text


# ---------------------------------------------------------------------------
# Test 5: historial ordenado created_at desc
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_history_ordered_desc() -> None:
    user = _FakeUser("gerente")
    repo = _FakeRepo()
    audit = _FakeAuditRepo()

    rule_a = _make_rule(code="rule_a", created_offset_hours=2)
    rule_b = _make_rule(code="rule_b", created_offset_hours=1)
    rule_c = _make_rule(code="rule_c", created_offset_hours=0)

    for r in [rule_a, rule_b, rule_c]:
        repo.seed(r)

    app = _make_app(user, repo, audit)

    with (
        patch("app.api.routes.exception_rules.ExceptionRuleRepository", return_value=repo),
        patch("app.api.routes.exception_rules.AuditRepository", return_value=audit),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/exception-rules/history")

    assert resp.status_code == 200, resp.text
    items = resp.json()
    codes = [item["code"] for item in items]
    assert codes == ["rule_c", "rule_b", "rule_a"]


# ---------------------------------------------------------------------------
# Test 6: activar regla inexistente → 404
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_activate_not_found_returns_404() -> None:
    user = _FakeUser("gerente")
    repo = _FakeRepo()  # vacío
    audit = _FakeAuditRepo()
    app = _make_app(user, repo, audit)

    nonexistent_id = uuid4()

    with (
        patch("app.api.routes.exception_rules.ExceptionRuleRepository", return_value=repo),
        patch("app.api.routes.exception_rules.AuditRepository", return_value=audit),
    ):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.patch(f"/exception-rules/{nonexistent_id}/activate")

    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["detail"]["code"] == "exception_rule_not_found"
