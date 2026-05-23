"""Tests unitarios del endpoint GET /api/v1/audit/verify (ADR-076 / R-005).

Estrategia:
- FastAPI ad-hoc con el router montado en /api/v1 (sin tocar app/main.py).
- Se overridean get_db_session y require_permissions.
- La sesión async se reemplaza por AsyncMock que devuelve filas mock.
- Se usa la función _compute_row_hash para generar hashes correctos en fixtures.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.audit import router as audit_router
from app.workers.tasks.audit_integrity import _compute_row_hash

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "auditor"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str] | None = None) -> None:
        self.id: UUID = uuid4()
        self.email = "auditor@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms or ["audit:read"])


# ---------------------------------------------------------------------------
# App fixture factory
# ---------------------------------------------------------------------------

_BASE_TIME = datetime(2026, 5, 11, 0, 0, 0, tzinfo=UTC)


def _make_mock_row(
    row_id: int,
    prev_hash: str,
    tamper: bool = False,
) -> MagicMock:
    event_at = _BASE_TIME + timedelta(seconds=row_id)
    payload_diff = {"amount": row_id * 5}
    correct_hash = _compute_row_hash(
        row_id=row_id,
        event_at=event_at,
        actor_id=None,
        entity_type="price",
        entity_id="sku-test",
        action="update",
        payload_diff=payload_diff,
        prev_hash=prev_hash,
    )
    row = MagicMock()
    row.id = row_id
    row.event_at = event_at
    row.actor_id = None
    row.entity_type = "price"
    row.entity_id = "sku-test"
    row.action = "update"
    row.payload_diff = payload_diff
    row.prev_hash = prev_hash
    row.current_hash = "badhash0" * 8 if tamper else correct_hash
    return row


def _build_app(rows: list[MagicMock]) -> FastAPI:
    """Construye una app FastAPI minimal con el router de audit y mocks de deps."""
    app = FastAPI()
    app.include_router(audit_router, prefix="/api/v1")

    fake_user = _FakeUser()

    async def _override_session():  # noqa: ANN202
        result_mock = MagicMock()
        result_mock.fetchall.return_value = rows
        session = AsyncMock()
        session.execute = AsyncMock(return_value=result_mock)
        yield session

    async def _override_user():  # noqa: ANN202
        return fake_user

    app.dependency_overrides[get_db_session] = _override_session
    app.dependency_overrides[get_current_user] = _override_user
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAuditVerifyEndpoint:
    @pytest.mark.asyncio
    async def test_verify_returns_200_for_clean_chain(self) -> None:
        """Chain limpia → HTTP 200 + verified=true."""
        rows = []
        running_hash = ""
        for i in range(1, 6):
            row = _make_mock_row(row_id=i, prev_hash=running_hash, tamper=False)
            running_hash = row.current_hash
            rows.append(row)

        app = _build_app(rows)

        from_str = (_BASE_TIME).isoformat()
        to_str = (_BASE_TIME + timedelta(days=1)).isoformat()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/audit/verify",
                params={"from": from_str, "to": to_str},
            )

        assert response.status_code == 200
        data = response.json()
        assert data["verified"] is True
        assert data["rows_checked"] == 5
        assert data["tampered_ids"] == []
        assert "checked_at" in data

    @pytest.mark.asyncio
    async def test_verify_returns_409_for_tampered(self) -> None:
        """Una fila tampered → HTTP 409 con tampered_ids no vacío."""
        rows = []
        running_hash = ""
        for i in range(1, 4):
            row = _make_mock_row(row_id=i, prev_hash=running_hash, tamper=False)
            running_hash = row.current_hash
            rows.append(row)
        # Insertar fila tampered
        tampered = _make_mock_row(row_id=99, prev_hash=running_hash, tamper=True)
        rows.append(tampered)

        app = _build_app(rows)

        from_str = (_BASE_TIME).isoformat()
        to_str = (_BASE_TIME + timedelta(days=1)).isoformat()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/audit/verify",
                params={"from": from_str, "to": to_str},
            )

        assert response.status_code == 409
        detail = response.json()["detail"]
        assert detail["code"] == "audit_tamper_detected"
        assert 99 in detail["tampered_ids"]

    @pytest.mark.asyncio
    async def test_verify_rejects_range_over_7_days(self) -> None:
        """Rango de 8 días → HTTP 422."""
        app = _build_app([])

        from_str = (_BASE_TIME - timedelta(days=8)).isoformat()
        to_str = _BASE_TIME.isoformat()

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get(
                "/api/v1/audit/verify",
                params={"from": from_str, "to": to_str},
            )

        assert response.status_code == 422
        detail = response.json()["detail"]
        # Puede ser dict (nuestra validación) o lista (pydantic)
        if isinstance(detail, dict):
            assert detail.get("code") == "range_too_large"
