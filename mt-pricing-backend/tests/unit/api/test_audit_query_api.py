"""Unit tests del router `app.api.routes.audit_query`.

US-1A-07-03 backend — `GET /api/v1/audit-events?entity_type=&entity_id=&...`.

Estrategia (alineada con `test_translations_workflow_api.py`):
- Monta una FastAPI ad-hoc con SOLO el router de audit_query.
- Override de `get_current_user`, `get_db_session`, y los closures
  generados por `require_permissions("audit:read")`.
- Stub `AuditQueryService` con resultados in-memory.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.audit_query import router as audit_query_router
from app.services.audit.audit_query_service import (
    AuditQueryFilters,
    AuditQueryResult,
    AuditQueryResultRow,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _Role:
    def __init__(self, perms: list[str]) -> None:
        self.code = "gerente"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str] | None = None) -> None:
        self.id: UUID = uuid4()
        self.email = "gerente@mt.ae"
        self.is_active = True
        self.role = _Role(perms or ["audit:read"])


class _FakeAuditQueryService:
    """Stub del servicio que captura los filters y devuelve canned rows."""

    def __init__(self, rows: list[AuditQueryResultRow] | None = None) -> None:
        self.rows = rows or []
        self.captured_filters: AuditQueryFilters | None = None
        self.captured_cursor: Any = None
        self.captured_limit: int | None = None

    async def query(
        self,
        filters: AuditQueryFilters,
        *,
        cursor: Any = None,
        limit: int = 50,
    ) -> AuditQueryResult:
        self.captured_filters = filters
        self.captured_cursor = cursor
        self.captured_limit = limit
        return AuditQueryResult(items=self.rows, next_cursor=None)


# ---------------------------------------------------------------------------
# Builders
# ---------------------------------------------------------------------------
def _build_app(user: _FakeUser, fake_service: _FakeAuditQueryService) -> FastAPI:
    app = FastAPI()
    app.include_router(audit_query_router, prefix="/api/v1")

    async def _override_db() -> Any:  # pragma: no cover
        yield None

    async def _override_user() -> _FakeUser:
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    # Override de los closures `_check` generados por require_permissions(...)
    for route in audit_query_router.routes:
        dep = getattr(route, "dependant", None)
        if dep is None:
            continue
        for d in dep.dependencies:
            call = d.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call: Any = call) -> _FakeUser:
                    return user

                app.dependency_overrides[call] = _allow

    # Monkey-patch del constructor del servicio dentro del router para
    # devolver siempre el fake. Como el router instancia
    # `AuditQueryService(session)` directamente, parcheamos en el módulo.
    import app.api.routes.audit_query as audit_query_module

    audit_query_module.AuditQueryService = lambda _session: fake_service  # type: ignore[assignment]
    return app


def _row(
    *,
    id: str = "1",
    entity_type: str = "products",
    entity_id: str = "MT-V-038",
    action: str = "product.created",
    actor_email: str | None = "u@mt.ae",
) -> AuditQueryResultRow:
    return AuditQueryResultRow(
        id=id,
        event_at=datetime.now(tz=UTC),
        entity_type=entity_type,
        entity_id=entity_id,
        action=action,
        actor_id=uuid4(),
        actor_email=actor_email,
        actor_full_name="Tester",
        before=None,
        after={"name": "x"},
        payload_diff={},
        reason=None,
    )


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_audit_events_returns_items_no_filters() -> None:
    rows = [_row(id="1"), _row(id="2", action="product.updated")]
    svc = _FakeAuditQueryService(rows)
    user = _FakeUser()
    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body["items"]) == 2
    assert body["items"][0]["entity_type"] == "products"
    assert body["page_size"] == 50


async def test_audit_events_csv_entity_type_parsed() -> None:
    svc = _FakeAuditQueryService([])
    user = _FakeUser()
    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events?entity_type=products,costs,prices")
    assert resp.status_code == 200
    assert svc.captured_filters is not None
    assert svc.captured_filters.entity_types == ("products", "costs", "prices")


async def test_audit_events_related_sku_passes_filter() -> None:
    svc = _FakeAuditQueryService([])
    user = _FakeUser()
    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events?related_sku=MT-V-038")
    assert resp.status_code == 200
    assert svc.captured_filters is not None
    assert svc.captured_filters.related_sku == "MT-V-038"


async def test_audit_events_actor_uuid_parsed() -> None:
    svc = _FakeAuditQueryService([])
    user = _FakeUser()
    app = _build_app(user, svc)
    actor_id = uuid4()
    async with await _client(app) as ac:
        resp = await ac.get(f"/api/v1/audit-events?actor={actor_id}")
    assert resp.status_code == 200
    assert svc.captured_filters is not None
    assert svc.captured_filters.actor_id == actor_id
    assert svc.captured_filters.actor_email is None


async def test_audit_events_actor_email_falls_back_when_not_uuid() -> None:
    svc = _FakeAuditQueryService([])
    user = _FakeUser()
    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events?actor=paula@")
    assert resp.status_code == 200
    assert svc.captured_filters is not None
    assert svc.captured_filters.actor_id is None
    assert svc.captured_filters.actor_email == "paula@"


async def test_audit_events_temporal_range_parsed() -> None:
    svc = _FakeAuditQueryService([])
    user = _FakeUser()
    app = _build_app(user, svc)
    since = (datetime.now(tz=UTC) - timedelta(days=7)).isoformat()
    until = datetime.now(tz=UTC).isoformat()
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events", params={"from": since, "to": until})
    assert resp.status_code == 200, resp.text
    assert svc.captured_filters is not None
    assert svc.captured_filters.since is not None
    assert svc.captured_filters.until is not None


async def test_audit_events_limit_max_200() -> None:
    svc = _FakeAuditQueryService([])
    user = _FakeUser()
    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events?limit=300")
    # FastAPI/Pydantic enforce le=200 → 422 esperado.
    assert resp.status_code == 422


async def test_audit_events_invalid_cursor_returns_400() -> None:
    svc = _FakeAuditQueryService([])
    user = _FakeUser()
    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events?cursor=not_base64!!")
    assert resp.status_code == 400
    assert resp.json()["detail"]["code"] == "invalid_cursor"


async def test_audit_events_action_csv_parsed() -> None:
    svc = _FakeAuditQueryService([])
    user = _FakeUser()
    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events?action=price.proposed,price.approved")
    assert resp.status_code == 200
    assert svc.captured_filters is not None
    assert svc.captured_filters.actions == ("price.proposed", "price.approved")


async def test_audit_events_actor_field_present_when_email() -> None:
    rows = [_row(actor_email="x@mt.ae")]
    svc = _FakeAuditQueryService(rows)
    user = _FakeUser()
    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/audit-events")
    body = resp.json()
    assert body["items"][0]["actor"] is not None
    assert body["items"][0]["actor"]["email"] == "x@mt.ae"
