"""Unit tests para GET /api/v1/comparator/dataset/export (US-F15-03-01).

Estrategia:
- FastAPI ad-hoc con dataset_router (no la app real).
- Se overridean get_db_session, get_current_user y require_permissions.
- La sesión se reemplaza por un mock AsyncSession cuyo execute() devuelve
  filas sintéticas.
- test_cli_validate_detects_duplicates testea la lógica pura _validate_file
  sin DB.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.matches import dataset_router

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers — fake DB rows
# ---------------------------------------------------------------------------
def _make_row(
    *,
    product_sku: str = "MTBR4001050",
    label: str = "accept",
    status: str = "validated",
    title: str = "Ball Valve DN50",
    specs_jsonb: dict | None = None,
) -> MagicMock:
    row = MagicMock()
    row.id = uuid4()
    row.product_sku = product_sku
    row.label = label
    row.status = status
    row.title = title
    row.specs_jsonb = specs_jsonb or {}
    return row


def _make_scalars_result(rows: list[Any]) -> MagicMock:
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = rows
    return scalars_mock


class _FakeRole:
    def __init__(self) -> None:
        self.code = "tester"
        self.permissions_snapshot = ["matches:read", "matches:write"]


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole()


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def _build_app(session_mock: Any) -> tuple[FastAPI, _FakeUser]:
    app = FastAPI()
    app.include_router(dataset_router, prefix="/api/v1")

    user = _FakeUser()

    async def _override_db():
        yield session_mock

    async def _override_user():
        return user

    def _override_perms(*_codes: str):
        async def _ok():
            return user

        return _ok

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    # Override all require_permissions closures registered on routes
    for route in dataset_router.routes:
        for dep in getattr(getattr(route, "dependant", None), "dependencies", []):
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):  # noqa: ARG001
                    return user

                app.dependency_overrides[call] = _allow

    return app, user


def _make_session(count: int, rows: list[Any]) -> AsyncMock:
    """Returns an AsyncSession mock.

    First execute() call returns the COUNT result.
    Second execute() call returns the scalars result (for streaming).
    """
    session = AsyncMock()

    # COUNT result
    count_result = MagicMock()
    count_result.scalar_one.return_value = count

    # Scalars result (for streaming rows)
    scalars_result = MagicMock()
    scalars_result.scalars.return_value = _make_scalars_result(rows)

    session.execute = AsyncMock(side_effect=[count_result, scalars_result])
    return session


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_export_returns_jsonl_when_sufficient_pairs() -> None:
    """Cuando hay >= min_pairs pares debe devolver 200 con Content-Type NDJSON."""
    # Build 1000 fake rows
    rows = [
        _make_row(
            product_sku=f"SKU{i:04d}",
            label="accept" if i % 2 == 0 else "reject",
        )
        for i in range(1000)
    ]
    session = _make_session(1000, rows)
    app, _ = _build_app(session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/v1/comparator/dataset/export",
            params={"format": "jsonl", "min_pairs": 1000},
        )

    assert resp.status_code == 200
    assert "application/x-ndjson" in resp.headers.get("content-type", "")
    lines = [ln for ln in resp.text.splitlines() if ln.strip()]
    assert len(lines) == 1000
    first = json.loads(lines[0])
    assert set(first.keys()) == {"sku_mt", "candidate_id", "title", "specs_jsonb", "label"}
    assert first["label"] in (0, 1)


@pytest.mark.asyncio
async def test_export_422_when_insufficient_pairs() -> None:
    """Cuando hay < min_pairs pares debe devolver 422 con error 'insufficient_pairs'."""
    session = _make_session(500, [])
    app, _ = _build_app(session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/v1/comparator/dataset/export",
            params={"format": "jsonl", "min_pairs": 1000},
        )

    assert resp.status_code == 422
    body = resp.json()
    detail = body["detail"]
    assert detail["error"] == "insufficient_pairs"
    assert detail["available"] == 500
    assert detail["required"] == 1000


@pytest.mark.asyncio
async def test_export_label_mapping() -> None:
    """'accept' → 1, 'reject' → 0 en el JSONL generado."""
    rows = [
        _make_row(product_sku="SKUA001", label="accept"),
        _make_row(product_sku="SKUR001", label="reject"),
    ]
    session = _make_session(2, rows)
    app, _ = _build_app(session)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        resp = await client.get(
            "/api/v1/comparator/dataset/export",
            params={"format": "jsonl", "min_pairs": 1},
        )

    assert resp.status_code == 200
    parsed = [json.loads(ln) for ln in resp.text.splitlines() if ln.strip()]
    labels_by_sku = {p["sku_mt"]: p["label"] for p in parsed}
    assert labels_by_sku["SKUA001"] == 1
    assert labels_by_sku["SKUR001"] == 0


def test_cli_validate_detects_duplicates() -> None:
    """_validate_file debe emitir WARNING para (sku_mt, candidate_id) duplicados."""
    from scripts.poc.export_dataset import _validate_file

    cid = str(uuid4())
    line_a = json.dumps(
        {
            "sku_mt": "SKU001",
            "candidate_id": cid,
            "title": "Product A",
            "specs_jsonb": {},
            "label": 1,
        }
    )
    line_b = json.dumps(
        {
            "sku_mt": "SKU001",
            "candidate_id": cid,  # duplicate key
            "title": "Product A duplicate",
            "specs_jsonb": {},
            "label": 0,
        }
    )
    # Non-duplicate line to keep ratio near 0.5
    line_c = json.dumps(
        {
            "sku_mt": "SKU002",
            "candidate_id": str(uuid4()),
            "title": "Product C",
            "specs_jsonb": {},
            "label": 0,
        }
    )

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".jsonl", delete=False, encoding="utf-8"
    ) as fh:
        fh.write(line_a + "\n")
        fh.write(line_b + "\n")
        fh.write(line_c + "\n")
        tmp_path = Path(fh.name)

    import io
    import sys

    captured_stderr = io.StringIO()
    old_stderr = sys.stderr
    sys.stderr = captured_stderr
    try:
        # Should still return True (duplicates are warnings, not fatal errors)
        result = _validate_file(tmp_path)
    finally:
        sys.stderr = old_stderr
        tmp_path.unlink(missing_ok=True)

    stderr_output = captured_stderr.getvalue()
    assert "WARNING" in stderr_output
    assert "duplicado" in stderr_output
    # Duplicate alone does not abort validation
    assert result is True
