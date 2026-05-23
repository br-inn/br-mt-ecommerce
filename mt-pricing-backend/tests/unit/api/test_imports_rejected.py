"""Unit tests — GET /imports/{run_id}/rejected-rows.

Patrón análogo a test_admin_flags_api:
- FastAPI ad-hoc con el router montado.
- Manipula _RUN_STORE directamente (in-memory, igual que el wizard).
- Sin DB real.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.imports import router as imports_router
from app.services.importer.importer_service import (
    ImportRunState,
    RejectedRow,
    _RUN_STORE,
    reset_run_store,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str]) -> None:
        self.id = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms)


def _build_app(user: _FakeUser) -> FastAPI:
    app = FastAPI()
    app.include_router(imports_router, prefix="/api/v1")

    fake_session = MagicMock()

    async def _override_db():
        yield fake_session

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    # Override require_permissions closures (los _check son closures únicas).
    for route in imports_router.routes:
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


def _make_run_with_rejected(rejected: list[RejectedRow]) -> ImportRunState:
    """Crea un ImportRunState sintético con filas rechazadas."""
    return ImportRunState(
        run_id="test_run_001",
        type_="pim",
        filename="test.xlsx",
        status="preview_ready",
        created_at=datetime.now(tz=timezone.utc),
        created_by="tester@mt.ae",
        summary={"total": 1250, "create": 100, "update": 50, "error": len(rejected)},
        rejected_rows=rejected,
    )


@pytest.fixture(autouse=True)
def _clear_run_store() -> None:
    """Limpia el _RUN_STORE antes y después de cada test."""
    reset_run_store()
    yield
    reset_run_store()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_rejected_rows_returns_404_for_unknown_run() -> None:
    """run_id inexistente → HTTP 404."""
    user = _FakeUser(perms=["imports:read"])
    app = _build_app(user)

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/imports/nonexistent_run_xyz/rejected-rows")

    assert resp.status_code == 404
    body = resp.json()
    assert body["detail"]["code"] == "import_run_not_found"


async def test_rejected_rows_returns_list() -> None:
    """Run con rejected rows → response con lista correcta."""
    user = _FakeUser(perms=["imports:read"])
    app = _build_app(user)

    rejected = [
        RejectedRow(row_number=5, sku="BAD001", reasons=["name_en vacío", "price_cost negativo"]),
        RejectedRow(row_number=12, sku=None, reasons=["parse_error"]),
    ]
    state = _make_run_with_rejected(rejected)
    _RUN_STORE["test_run_001"] = state

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/imports/test_run_001/rejected-rows")

    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["run_id"] == "test_run_001"
    assert body["total_rows"] == 1250
    assert body["rejected_count"] == 2

    rows: list[dict[str, Any]] = body["rejected_rows"]
    assert len(rows) == 2

    # Primera fila rechazada
    assert rows[0]["row_number"] == 5
    assert rows[0]["sku"] == "BAD001"
    assert "name_en vacío" in rows[0]["reasons"]
    assert "price_cost negativo" in rows[0]["reasons"]

    # Segunda fila rechazada (sku None → null en JSON)
    assert rows[1]["row_number"] == 12
    assert rows[1]["sku"] is None
    assert rows[1]["reasons"] == ["parse_error"]


async def test_rejected_rows_empty_when_no_errors() -> None:
    """Run sin filas rechazadas → rejected_count=0, lista vacía."""
    user = _FakeUser(perms=["imports:read"])
    app = _build_app(user)

    state = _make_run_with_rejected([])
    _RUN_STORE["test_run_001"] = state

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/imports/test_run_001/rejected-rows")

    assert resp.status_code == 200
    body = resp.json()
    assert body["rejected_count"] == 0
    assert body["rejected_rows"] == []
