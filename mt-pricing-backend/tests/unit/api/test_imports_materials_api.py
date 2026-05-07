"""Unit tests del router `app.api.routes.imports_materials` (sin DB ni JWT real)."""

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
from app.api.routes.imports_materials import (
    reset_run_store,
    router as imports_materials_router,
)

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
        self.role = _FakeRole(["imports:read", "imports:write"])


def _make_xlsx(header: list, rows: list[list]) -> bytes:
    wb = Workbook()
    ws = wb.active
    ws.append(header)
    for r in rows:
        ws.append(r)
    bio = io.BytesIO()
    wb.save(bio)
    return bio.getvalue()


def _build_app() -> tuple[FastAPI, _FakeUser, MagicMock]:
    """Construye FastAPI ad-hoc con deps overridden.

    El ``get_db_session`` se override-a a una session que pasa por el
    repository real — pero el repository hace ``execute`` que también
    interceptamos con un mock. Para simplificar, override-amos el repo
    monkeypatching ``MaterialCompatibilitiesRepository`` en el módulo
    para que no se construya un repo real (mock asyncSession + repo mock).

    Estrategia: pasamos un ``fake_session`` que no se usa porque
    monkey-patchamos ``MaterialCompatibilitiesRepository`` en el router al
    cargar la fixture.
    """
    reset_run_store()
    app = FastAPI()
    app.include_router(imports_materials_router, prefix="/api/v1")

    user = _FakeUser()

    repo_mock = MagicMock()
    repo_mock.replace_all = AsyncMock(return_value=2)
    repo_mock.insert_many = AsyncMock(return_value=2)

    fake_session = MagicMock()

    async def _override_db():
        yield fake_session

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
                if (
                    fn.__module__ == require_permissions.__module__
                    and fn.__qualname__.startswith("require_permissions.")
                ):
                    app.dependency_overrides[fn] = _override_perms_factory()

    # Monkey-patch repo en el router para que no toque BD.
    import app.api.routes.imports_materials as router_module

    original_repo = router_module.MaterialCompatibilitiesRepository
    router_module.MaterialCompatibilitiesRepository = (  # type: ignore[assignment]
        lambda _session: repo_mock
    )
    app.state._restore_repo = (router_module, original_repo)  # type: ignore[attr-defined]
    return app, user, repo_mock


def _restore(app: FastAPI) -> None:
    mod, original = app.state._restore_repo  # type: ignore[attr-defined]
    mod.MaterialCompatibilitiesRepository = original


async def test_preview_summary_and_columns() -> None:
    app, _, _ = _build_app()
    xlsx = _make_xlsx(
        ["producto_descriptor", "temperatura_c", "Acero 316L", "PVC"],
        [["Ácido sulfúrico", 20, "OK", "X"], ["Agua", 25, "OK", "OK"]],
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as cli:
            resp = await cli.post(
                "/api/v1/imports/materials/preview",
                files={"file": ("m.xlsx", xlsx, "application/octet-stream")},
            )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["kind"] == "materials"
        assert body["status"] == "preview_ready"
        assert body["summary"]["total"] == 2
        assert body["summary"]["ok"] == 2
        assert "acero_316l" in body["materials_columns"]
        assert "pvc" in body["materials_columns"]
    finally:
        _restore(app)


async def test_apply_replace_truncates() -> None:
    app, _, repo_mock = _build_app()
    xlsx = _make_xlsx(
        ["producto_descriptor", "temperatura_c", "PVC"],
        [["A", 10, "OK"], ["B", 20, "OK"]],
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as cli:
            resp = await cli.post(
                "/api/v1/imports/materials/preview",
                files={"file": ("m.xlsx", xlsx, "application/octet-stream")},
            )
            run_id = resp.json()["run_id"]
            resp_apply = await cli.post(
                f"/api/v1/imports/materials/{run_id}/apply",
                json={"mode": "replace"},
            )
        assert resp_apply.status_code == 200, resp_apply.text
        body = resp_apply.json()
        assert body["status"] == "completed"
        assert body["apply"]["truncated"] is True
        assert body["apply"]["inserted"] == 2
        repo_mock.replace_all.assert_awaited_once()
    finally:
        _restore(app)


async def test_apply_append_mode() -> None:
    app, _, repo_mock = _build_app()
    xlsx = _make_xlsx(
        ["producto_descriptor", "temperatura_c", "PVC"],
        [["A", 10, "OK"]],
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as cli:
            resp = await cli.post(
                "/api/v1/imports/materials/preview",
                files={"file": ("m.xlsx", xlsx, "application/octet-stream")},
            )
            run_id = resp.json()["run_id"]
            resp_apply = await cli.post(
                f"/api/v1/imports/materials/{run_id}/apply",
                json={"mode": "append"},
            )
        assert resp_apply.status_code == 200, resp_apply.text
        body = resp_apply.json()
        assert body["apply"]["truncated"] is False
        repo_mock.insert_many.assert_awaited()
    finally:
        _restore(app)


async def test_status_404() -> None:
    app, _, _ = _build_app()
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as cli:
            resp = await cli.get("/api/v1/imports/materials/deadbeef/status")
        assert resp.status_code == 404
    finally:
        _restore(app)


async def test_invalid_header_returns_422() -> None:
    app, _, _ = _build_app()
    xlsx = _make_xlsx(
        ["wrong_left_header", "temp"],
        [["A", 10]],
    )
    transport = ASGITransport(app=app)
    try:
        async with AsyncClient(transport=transport, base_url="http://t") as cli:
            resp = await cli.post(
                "/api/v1/imports/materials/preview",
                files={"file": ("m.xlsx", xlsx, "application/octet-stream")},
            )
        assert resp.status_code == 422
    finally:
        _restore(app)
