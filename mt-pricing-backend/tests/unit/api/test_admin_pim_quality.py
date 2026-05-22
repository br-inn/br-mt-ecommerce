"""Unit tests — GET /admin/pim/data-quality (admin_pim_quality router).

Patrón análogo a test_admin_flags_api:
- FastAPI ad-hoc con el router montado.
- Override de get_db_session y require_permissions.
- Sin DB real — mock de _compute_data_quality.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.admin_pim_quality import router as pim_quality_router

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
    app.include_router(pim_quality_router, prefix="/api/v1")

    fake_session = MagicMock()

    async def _override_db():
        yield fake_session

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user

    # Override require_permissions closures (los _check son closures únicas).
    for route in pim_quality_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):
                    return user

                app.dependency_overrides[call] = _allow

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


def _mock_report(total: int = 100, missing_name_en: int = 22) -> dict[str, Any]:
    """Construye un reporte sintético para tests."""
    return {
        "total_skus": total,
        "gaps": {
            "missing_name_en": {
                "count": missing_name_en,
                "pct": round(missing_name_en / total * 100, 1),
                "sample_skus": ["SKU001", "SKU002"],
            },
            "missing_specs": {
                "count": 37,
                "pct": 37.0,
                "sample_skus": ["SKU010"],
            },
            "missing_images": {
                "count": 10,
                "pct": 10.0,
                "sample_skus": [],
            },
            "missing_brand": {
                "count": 3,
                "pct": 3.0,
                "sample_skus": ["SKU030"],
            },
            "missing_family": {
                "count": 0,
                "pct": 0.0,
                "sample_skus": [],
            },
            "specs_below_threshold": {
                "count": 15,
                "pct": 15.0,
                "threshold": 3,
                "sample_skus": [],
                "description": "specs JSONB con menos de 3 campos",
            },
        },
        "generated_at": "2026-05-12T10:00:00+00:00",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_data_quality_returns_structure() -> None:
    """Mock DB con 100 SKUs, 22 sin traducción → response con estructura correcta."""
    user = _FakeUser(perms=["pim:read", "admin:read"])
    app = _build_app(user)

    report = _mock_report(total=100, missing_name_en=22)

    with patch(
        "app.api.routes.admin_pim_quality._compute_data_quality",
        new=AsyncMock(return_value=report),
    ):
        async with await _client(app) as ac:
            resp = await ac.get("/api/v1/admin/pim/data-quality")

    assert resp.status_code == 200, resp.text
    body = resp.json()

    # Estructura de alto nivel
    assert "total_skus" in body
    assert "gaps" in body
    assert "generated_at" in body
    assert body["total_skus"] == 100

    gaps = body["gaps"]
    # Todas las claves esperadas presentes
    for key in (
        "missing_name_en",
        "missing_specs",
        "missing_images",
        "missing_brand",
        "missing_family",
        "specs_below_threshold",
    ):
        assert key in gaps, f"gap '{key}' no está en la respuesta"

    # missing_name_en tiene la estructura correcta
    mne = gaps["missing_name_en"]
    assert "count" in mne
    assert "pct" in mne
    assert "sample_skus" in mne
    assert isinstance(mne["sample_skus"], list)

    # specs_below_threshold tiene campo threshold y description
    sbt = gaps["specs_below_threshold"]
    assert "threshold" in sbt
    assert "description" in sbt


async def test_data_quality_pct_calculation() -> None:
    """Verifica que el porcentaje de missing_name_en se calcule correctamente."""
    user = _FakeUser(perms=["pim:read", "admin:read"])
    app = _build_app(user)

    # 22 de 100 SKUs → 22.0%
    report = _mock_report(total=100, missing_name_en=22)

    with patch(
        "app.api.routes.admin_pim_quality._compute_data_quality",
        new=AsyncMock(return_value=report),
    ):
        async with await _client(app) as ac:
            resp = await ac.get("/api/v1/admin/pim/data-quality")

    assert resp.status_code == 200
    body = resp.json()
    mne = body["gaps"]["missing_name_en"]
    assert mne["count"] == 22
    assert mne["pct"] == pytest.approx(22.0, abs=0.1)

    # Verificamos también que sample_skus son strings
    for sku in mne["sample_skus"]:
        assert isinstance(sku, str)


async def test_data_quality_pct_with_zero_total() -> None:
    """Con 0 SKUs el porcentaje debe ser 0.0 sin división por cero."""
    user = _FakeUser(perms=["pim:read", "admin:read"])
    app = _build_app(user)

    # Reporte con 0 SKUs totales
    empty_report: dict[str, Any] = {
        "total_skus": 0,
        "gaps": {
            "missing_name_en": {"count": 0, "pct": 0.0, "sample_skus": []},
            "missing_specs": {"count": 0, "pct": 0.0, "sample_skus": []},
            "missing_images": {"count": 0, "pct": 0.0, "sample_skus": []},
            "missing_brand": {"count": 0, "pct": 0.0, "sample_skus": []},
            "missing_family": {"count": 0, "pct": 0.0, "sample_skus": []},
            "specs_below_threshold": {
                "count": 0,
                "pct": 0.0,
                "threshold": 3,
                "sample_skus": [],
                "description": "specs JSONB con menos de 3 campos",
            },
        },
        "generated_at": "2026-05-12T10:00:00+00:00",
    }

    with patch(
        "app.api.routes.admin_pim_quality._compute_data_quality",
        new=AsyncMock(return_value=empty_report),
    ):
        async with await _client(app) as ac:
            resp = await ac.get("/api/v1/admin/pim/data-quality")

    assert resp.status_code == 200
    body = resp.json()
    assert body["total_skus"] == 0
    for _key, gap in body["gaps"].items():
        assert gap["pct"] == 0.0
