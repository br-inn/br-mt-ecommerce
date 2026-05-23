"""Unit tests para `app.api.routes.pricing_admin` (US-1B-01-07).

Patrón idéntico a `test_pricing_engine_api.py`: overrides de get_db_session,
get_current_user, require_permissions. Sin DB ni Celery real.
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
from app.api.routes.pricing_admin import router as pricing_admin_router

pytestmark = pytest.mark.unit


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(["prices:propose", "audit:read"])


def _build_app(*, session: Any = None) -> tuple[FastAPI, _FakeUser]:
    app = FastAPI()
    app.include_router(pricing_admin_router, prefix="/api/v1")

    user = _FakeUser()

    async def _override_db():  # pragma: no cover
        yield session

    async def _override_user():
        return user

    def _override_perms_factory(*_codes: str):
        async def _ok():
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


# ---------------------------------------------------------------------------
# Trigger
# ---------------------------------------------------------------------------
async def test_trigger_bulk_recalc_queues_task(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mockea bulk_recalc_task.delay para evitar Celery."""
    from app.workers.tasks import pricing_recalc as recalc_mod

    fake_task = MagicMock()
    fake_task.delay = MagicMock(return_value=MagicMock(id="task-xyz"))
    monkeypatch.setattr(recalc_mod, "bulk_recalc_task", fake_task, raising=True)

    app, _ = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/pricing/admin/bulk-recalc/trigger",
            json={"reason": "FX update", "source": "manual_admin"},
        )
    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["task_id"] == "task-xyz"
    assert body["source"] == "manual_admin"
    assert body["status"] == "queued"
    fake_task.delay.assert_called_once_with("manual_admin")


async def test_trigger_bulk_recalc_default_source(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.workers.tasks import pricing_recalc as recalc_mod

    fake_task = MagicMock()
    fake_task.delay = MagicMock(return_value=MagicMock(id="task-default"))
    monkeypatch.setattr(recalc_mod, "bulk_recalc_task", fake_task, raising=True)

    app, _ = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post("/api/v1/pricing/admin/bulk-recalc/trigger", json={})
    assert resp.status_code == 202
    body = resp.json()
    assert body["source"] == "manual_admin"


# ---------------------------------------------------------------------------
# Last run
# ---------------------------------------------------------------------------
async def test_last_run_returns_not_found_when_empty() -> None:
    fake_session = MagicMock()
    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=None)
    fake_session.execute = AsyncMock(return_value=fake_result)

    app, _ = _build_app(session=fake_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.get("/api/v1/pricing/admin/bulk-recalc/last-run")

    assert resp.status_code == 200
    body = resp.json()
    assert body["found"] is False
    assert body["summary"] is None


async def test_last_run_returns_event_summary() -> None:
    fake_session = MagicMock()
    last_event = MagicMock()
    last_event.event_at = datetime(2026, 5, 7, 2, 0, tzinfo=timezone.utc)
    last_event.actor_email = "system@mt.ae"
    last_event.after = {"skus_total": 224, "skus_processed": 220}
    last_event.payload_diff = {"source": "nightly_beat"}

    fake_result = MagicMock()
    fake_result.scalar_one_or_none = MagicMock(return_value=last_event)
    fake_session.execute = AsyncMock(return_value=fake_result)

    app, _ = _build_app(session=fake_session)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.get("/api/v1/pricing/admin/bulk-recalc/last-run")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["found"] is True
    assert body["summary"]["skus_total"] == 224
    assert body["actor_email"] == "system@mt.ae"
    assert body["source"] == "nightly_beat"
    assert body["event_at"].startswith("2026-05-07T02:00")


# ---------------------------------------------------------------------------
# OpenAPI metadata smoke
# ---------------------------------------------------------------------------
def test_routes_have_operation_id_and_tags() -> None:
    """US-1A-DEV-01: ambos endpoints tienen operation_id + tags + summary +
    description bien seteados para que `pnpm openapi:gen` produzca tipos
    nombrables."""
    routes_by_path = {r.path: r for r in pricing_admin_router.routes}  # type: ignore[attr-defined]
    trigger = routes_by_path["/pricing/admin/bulk-recalc/trigger"]
    last_run = routes_by_path["/pricing/admin/bulk-recalc/last-run"]
    assert trigger.operation_id == "pricingAdminTriggerBulkRecalc"  # type: ignore[attr-defined]
    assert last_run.operation_id == "pricingAdminGetBulkRecalcLastRun"  # type: ignore[attr-defined]
    assert trigger.tags == ["pricing-admin"]  # type: ignore[attr-defined]
    assert trigger.summary  # type: ignore[attr-defined]
    assert trigger.description  # type: ignore[attr-defined]
