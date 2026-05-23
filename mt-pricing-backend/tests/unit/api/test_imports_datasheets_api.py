"""Unit tests del router `app.api.routes.imports_datasheets` (US-1A-06-04)."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.imports_datasheets import (
    get_importer_datasheets_service,
    get_product_service,
    router as imports_datasheets_router,
)
from app.services.importer_datasheets import ImporterDatasheetsService
from app.services.importer_datasheets.importer_service import (
    reset_datasheets_run_store,
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
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(["imports:read", "imports:write"])


def _mk_pdf(text: str) -> bytes:
    return (
        b"%PDF-1.4\n"
        b"1 0 obj << /Type /Catalog >> endobj\n"
        b"BT (" + text.encode("utf-8") + b") Tj ET\n"
        b"%%EOF\n"
    )


class _FakeSkuResolver:
    def __init__(self, mapping: dict[str, str]) -> None:
        self.mapping = dict(mapping)

    async def resolve_skus(self, suffixes: Any) -> dict[str, str]:
        return {s: self.mapping[s] for s in suffixes if s in self.mapping}


def _build_app(
    *, sku_mapping: dict[str, str] | None = None
) -> tuple[FastAPI, _FakeUser, MagicMock]:
    reset_datasheets_run_store()
    app = FastAPI()
    app.include_router(imports_datasheets_router, prefix="/api/v1")

    user = _FakeUser()
    fake_session = MagicMock()
    sku_resolver = _FakeSkuResolver(sku_mapping or {})
    service = ImporterDatasheetsService(fake_session, sku_resolver=sku_resolver)

    product_service = MagicMock()
    product_service.attach_datasheet = AsyncMock(return_value=MagicMock(id=uuid4()))

    async def _override_db():  # pragma: no cover
        yield None

    async def _override_user():
        return user

    def _override_perms_factory(*_codes: str):
        async def _ok():
            return user

        return _ok

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_importer_datasheets_service] = lambda: service
    app.dependency_overrides[get_product_service] = lambda: product_service

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

    return app, user, product_service


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_preview_single_pdf_match() -> None:
    app, _, _ = _build_app(sku_mapping={"5114": "MT-V-5114"})
    payload = _mk_pdf("DN50 PN16 brass body")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/datasheets/preview",
            files={"files": ("MTFT_5114.pdf", payload, "application/pdf")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["kind"] == "datasheets"
    assert body["status"] == "preview_ready"
    assert body["summary"]["total_files"] == 1
    assert body["summary"]["matched_diffs"] == 1
    assert body["orphan_files"] == []
    assert body["orphan_skus"] == []
    assert body["samples"][0]["product_sku"] == "MT-V-5114"
    assert body["samples"][0]["specs"]["dn"] == "DN50"


async def test_preview_invalid_filename_orphans() -> None:
    app, _, _ = _build_app()
    payload = _mk_pdf("foo")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/datasheets/preview",
            files={"files": ("random.pdf", payload, "application/pdf")},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["summary"]["matched_diffs"] == 0
    assert len(body["orphan_files"]) == 1
    assert body["orphan_files"][0]["filename"] == "random.pdf"


async def test_preview_unknown_suffix_orphan_skus() -> None:
    app, _, _ = _build_app(sku_mapping={})  # nada resuelve
    payload = _mk_pdf("DN50")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/datasheets/preview",
            files={"files": ("MTFT_9999.pdf", payload, "application/pdf")},
        )
    body = resp.json()
    assert body["summary"]["matched_diffs"] == 0
    assert "9999" in body["orphan_skus"]
    # El file también queda en orphan_files con reason='no_sku_resolved'
    assert any(o["reason"] == "no_sku_resolved" for o in body["orphan_files"])


async def test_apply_invokes_product_service() -> None:
    app, _, product_service = _build_app(sku_mapping={"5114": "MT-V-5114"})
    payload = _mk_pdf("DN50 PN16 brass")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/datasheets/preview",
            files={"files": ("MTFT_5114.pdf", payload, "application/pdf")},
        )
        run_id = resp.json()["run_id"]
        resp_apply = await cli.post(f"/api/v1/imports/datasheets/{run_id}/apply", json={})
    assert resp_apply.status_code == 200, resp_apply.text
    body = resp_apply.json()
    assert body["status"] == "completed"
    assert body["apply"]["attached"] == 1
    assert product_service.attach_datasheet.await_count == 1


async def test_status_404_for_unknown_run() -> None:
    app, _, _ = _build_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.get("/api/v1/imports/datasheets/deadbeef/status")
    assert resp.status_code == 404


async def test_apply_invalid_state_409() -> None:
    app, _, _ = _build_app(sku_mapping={"5114": "MT-V-5114"})
    payload = _mk_pdf("DN50")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/datasheets/preview",
            files={"files": ("MTFT_5114.pdf", payload, "application/pdf")},
        )
        run_id = resp.json()["run_id"]
        await cli.post(f"/api/v1/imports/datasheets/{run_id}/apply", json={})
        # Segundo apply → 409
        resp2 = await cli.post(f"/api/v1/imports/datasheets/{run_id}/apply", json={})
    assert resp2.status_code == 409


async def test_preview_multi_sku_filename() -> None:
    app, _, _ = _build_app(sku_mapping={"5114": "MT-V-5114", "5115": "MT-V-5115"})
    payload = _mk_pdf("DN50 PN16 brass")
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as cli:
        resp = await cli.post(
            "/api/v1/imports/datasheets/preview",
            files={"files": ("MTFT_5114-5115.pdf", payload, "application/pdf")},
        )
    body = resp.json()
    # un solo file pero dos diffs (uno por SKU)
    assert body["summary"]["total_files"] == 1
    assert body["summary"]["matched_diffs"] == 2
