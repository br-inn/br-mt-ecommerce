"""Unit tests del router `app.api.routes.imports_costs` (sin DB ni JWT real).

Estrategia (idéntica a test_matches_api.py):
- Monta una FastAPI ad-hoc que incluye el router con prefijo ``/api/v1`` —
  NO modificamos ``app/main.py`` ni ``app/api/routes/__init__.py``.
- Override de ``get_db_session``, ``get_current_user``, ``require_permissions``,
  ``get_importer_costs_service``, ``get_cost_service``.

Cobertura:
- ``POST /imports/costs/preview`` con xlsx válido → 200 + summary + orphans.
- ``POST /imports/costs/{run_id}/apply`` invoca CostService mockeado, no toca DB.
- ``GET /imports/costs/{run_id}/status`` devuelve estado.
- 404 si run_id desconocido.
- 422 si header inválido.
"""

from __future__ import annotations

import io
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from openpyxl import Workbook

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.imports_costs import (
    get_cost_service,
    get_importer_costs_service,
    router as imports_costs_router,
)
from app.services.importer_costs import (
    EXPECTED_COSTS_HEADERS,
    ImporterCostsService,
)
from app.services.importer_costs.importer_service import (
    reset_run_store,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(["imports:read", "imports:write"])


def _make_costs_xlsx(rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(list(EXPECTED_COSTS_HEADERS))
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _row(sku="SKU001", scheme="FBA", supplier="SUP-A", total="100.50"):
    return [
        sku,
        scheme,
        supplier,
        "AED",
        total,
        "80",
        "10",
        "5",
        "3",
        "0",
        "1",
        "0.5",
        "0.5",
        "0",
        "0.5",
        "2026-05-07",
    ]


def _build_app(*, with_orphans: bool = False) -> tuple[FastAPI, _FakeUser, MagicMock]:
    """Construye una FastAPI con todas las deps overridden.

    Retorna (app, fake_user, cost_service_mock) para inspección post-llamada.
    """
    reset_run_store()
    app = FastAPI()
    app.include_router(imports_costs_router, prefix="/api/v1")

    user = _FakeUser()

    async def _override_db():  # pragma: no cover — dummy
        yield None

    async def _override_user():
        return user

    def _override_perms_factory(*_codes: str):
        async def _ok():
            return user

        return _ok

    # CostService mock — no toca DB.
    cost_service = MagicMock()
    cost_service.create_cost = AsyncMock(return_value=MagicMock(id=uuid4()))

    # Stub session que sirve a compute_cost_diff.
    fake_session = MagicMock()

    call_counter = {"i": 0}

    async def _execute(stmt: Any) -> MagicMock:
        call_counter["i"] += 1
        idx = call_counter["i"]
        result = MagicMock()
        if idx == 1:
            # products: si with_orphans, no devolver el SKU.
            result.all.return_value = [] if with_orphans else [("SKU001",)]
        elif idx == 2:
            result.all.return_value = [("FBA",)]
        elif idx == 3:
            result.all.return_value = [("SUP-A",)]
        else:
            result.scalars.return_value.all.return_value = []
        return result

    fake_session.execute = AsyncMock(side_effect=_execute)
    service = ImporterCostsService(fake_session)

    def _override_service():
        return service

    def _override_cost_service():
        return cost_service

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_importer_costs_service] = _override_service
    app.dependency_overrides[get_cost_service] = _override_cost_service

    # require_permissions(...) returns a fresh callable per call site — walk
    # the router's dependants and override each closure that came from the
    # factory. Replicamos la técnica de test_matches_api.py.
    for route in app.routes:
        if hasattr(route, "dependant"):
            for dep in route.dependant.dependencies:
                if dep.call is None:
                    continue
                fn = dep.call
                if (
                    fn.__module__ == require_permissions.__module__
                    and fn.__qualname__.startswith("require_permissions.")
                ):
                    app.dependency_overrides[fn] = _override_perms_factory()

    return app, user, cost_service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_preview_returns_summary_and_orphans_zero() -> None:
    app, _, _ = _build_app()
    xlsx_bytes = _make_costs_xlsx([_row()])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/costs/preview",
            files={"file": ("c.xlsx", xlsx_bytes, "application/octet-stream")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "costs"
    assert body["status"] == "preview_ready"
    assert body["summary"]["total"] == 1
    assert body["summary"]["create"] == 1
    assert body["orphans"]["sku_not_in_pim"] == []


async def test_preview_orphans_reported() -> None:
    app, _, _ = _build_app(with_orphans=True)
    xlsx_bytes = _make_costs_xlsx([_row()])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/costs/preview",
            files={"file": ("c.xlsx", xlsx_bytes, "application/octet-stream")},
        )
    body = resp.json()
    assert body["orphans"]["sku_not_in_pim"] == ["SKU001"]
    assert body["summary"]["orphan"] == 1


async def test_preview_invalid_header_returns_422() -> None:
    app, _, _ = _build_app()
    wb = Workbook()
    ws = wb.active
    ws.append(["wrong", "headers"])
    ws.append(["a", "b"])
    bio = io.BytesIO()
    wb.save(bio)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/costs/preview",
            files={"file": ("c.xlsx", bio.getvalue(), "application/octet-stream")},
        )
    assert resp.status_code == 422


async def test_apply_invokes_cost_service() -> None:
    app, _, cost_service = _build_app()
    xlsx_bytes = _make_costs_xlsx([_row()])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/costs/preview",
            files={"file": ("c.xlsx", xlsx_bytes, "application/octet-stream")},
        )
        run_id = resp.json()["run_id"]
        resp_apply = await cli.post(f"/api/v1/imports/costs/{run_id}/apply", json={})
    assert resp_apply.status_code == 200, resp_apply.text
    body = resp_apply.json()
    assert body["status"] == "completed"
    assert body["apply"]["created"] == 1
    assert cost_service.create_cost.await_count == 1


async def test_status_404_for_unknown_run() -> None:
    app, _, _ = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.get("/api/v1/imports/costs/deadbeef/status")
    assert resp.status_code == 404


async def test_apply_invalid_state_returns_409() -> None:
    app, _, cost_service = _build_app()
    xlsx_bytes = _make_costs_xlsx([_row()])
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/costs/preview",
            files={"file": ("c.xlsx", xlsx_bytes, "application/octet-stream")},
        )
        run_id = resp.json()["run_id"]
        # Aplicar dos veces — segunda debe ser 409.
        await cli.post(f"/api/v1/imports/costs/{run_id}/apply", json={})
        resp2 = await cli.post(f"/api/v1/imports/costs/{run_id}/apply", json={})
    assert resp2.status_code == 409
