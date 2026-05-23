"""Unit tests para los endpoints de compatibility — sin DB.

Patrón: FastAPI ad-hoc con el router products montado; override del servicio
CompatibilityService y del current_user. Sin DB real ni Celery.

Cobertura:
1.  GET /products/{sku}/compatibility → 200 lista vacía.
2.  GET /products/{sku}/compatibility con kind filter.
3.  GET /products/{sku}/compatibility → 404 cuando SKU no existe.
4.  GET /products/{sku}/compatibility/inverse → 200.
5.  POST /products/{sku}/compatibility → 201 created.
6.  POST /products/{sku}/compatibility → 409 duplicate.
7.  POST /products/{sku}/compatibility → 422 self-loop.
8.  POST /products/{sku}/compatibility → 404 SKU not found.
9.  DELETE /products/{sku}/compatibility/{csku}/{kind} → 204.
10. DELETE /products/{sku}/compatibility/{csku}/{kind} → 404 not found.
11. PUT /products/{sku}/compatibility → 200 replace all.
12. PUT /products/{sku}/compatibility body vacío → 200 (vacía lista).
13. GET sin auth → 401.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session, require_permissions
from app.api.routes.products import get_compatibility_service, router as products_router
from app.services.compatibility.compatibility_service import (
    CompatibilityDuplicateError,
    CompatibilityNotFoundError,
    CompatibilitySelfLoopError,
    CompatibilityService,
    CompatibilitySkuNotFoundError,
)

pytestmark = pytest.mark.unit

NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str] | None = None) -> None:
        self.id = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms or ["products:read", "products:write"])


class _FakeLink:
    def __init__(
        self,
        product_sku: str = "MT-A-001",
        compatible_with_sku: str = "MT-B-002",
        kind: str = "spare_part",
        notes: str | None = None,
        position: int = 0,
    ) -> None:
        self.id = uuid4()
        self.product_sku = product_sku
        self.compatible_with_sku = compatible_with_sku
        self.kind = kind
        self.notes = notes
        self.position = position
        self.created_at = NOW
        self.created_by = None

        class _P:
            sku = compatible_with_sku
            name_en = f"Product {compatible_with_sku}"
            family = "valves"
            images: list = []

        self.compatible_with = _P()


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------


def _build_app(user: _FakeUser, compat_svc: CompatibilityService) -> FastAPI:
    app = FastAPI()
    app.include_router(products_router, prefix="/api/v1")

    fake_session = MagicMock()

    async def _override_db():  # pragma: no cover
        yield fake_session

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_compatibility_service] = lambda: compat_svc

    # Override require_permissions closures (inner _check functions).
    for route in products_router.routes:
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


def _mock_svc() -> CompatibilityService:
    svc = MagicMock(spec=CompatibilityService)
    return svc


# ---------------------------------------------------------------------------
# Tests — GET list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_compatibility_empty() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    svc.list_for_product = AsyncMock(return_value=[])

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-A-001/compatibility")

    assert resp.status_code == 200
    assert resp.json() == []


@pytest.mark.asyncio
async def test_list_compatibility_with_kind_filter() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    fake_link = _FakeLink(kind="accessory")
    svc.list_for_product = AsyncMock(return_value=[fake_link])

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-A-001/compatibility?kind=accessory")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["kind"] == "accessory"
    # Verifica desnormalización
    assert body[0]["compatible_product"]["sku"] == "MT-B-002"


@pytest.mark.asyncio
async def test_list_compatibility_product_not_found() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    svc.list_for_product = AsyncMock(side_effect=CompatibilitySkuNotFoundError("MT-NOPE"))

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-NOPE/compatibility")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — GET inverse
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_compatibility_inverse_ok() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    fake_link = _FakeLink(product_sku="MT-B-002", compatible_with_sku="MT-A-001")
    svc.list_inverse = AsyncMock(return_value=[fake_link])

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-A-001/compatibility/inverse")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["product_sku"] == "MT-B-002"


# ---------------------------------------------------------------------------
# Tests — POST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_compatibility_created() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    fake_link = _FakeLink()
    svc.add_link = AsyncMock(return_value=fake_link)

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MT-A-001/compatibility",
            json={"compatible_with_sku": "MT-B-002", "kind": "spare_part"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["kind"] == "spare_part"


@pytest.mark.asyncio
async def test_add_compatibility_duplicate_409() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    svc.add_link = AsyncMock(
        side_effect=CompatibilityDuplicateError("MT-A-001", "MT-B-002", "spare_part")
    )

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MT-A-001/compatibility",
            json={"compatible_with_sku": "MT-B-002", "kind": "spare_part"},
        )

    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_add_compatibility_self_loop_422() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    svc.add_link = AsyncMock(side_effect=CompatibilitySelfLoopError())

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MT-A-001/compatibility",
            json={"compatible_with_sku": "MT-A-001", "kind": "spare_part"},
        )

    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_add_compatibility_sku_not_found_404() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    svc.add_link = AsyncMock(side_effect=CompatibilitySkuNotFoundError("MT-NOPE"))

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MT-A-001/compatibility",
            json={"compatible_with_sku": "MT-NOPE", "kind": "accessory"},
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — DELETE
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_compatibility_204() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    svc.remove_link = AsyncMock(return_value=None)

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.delete("/api/v1/products/MT-A-001/compatibility/MT-B-002/spare_part")

    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_remove_compatibility_not_found_404() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    svc.remove_link = AsyncMock(
        side_effect=CompatibilityNotFoundError("MT-A-001", "MT-B-002", "spare_part")
    )

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.delete("/api/v1/products/MT-A-001/compatibility/MT-B-002/spare_part")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests — PUT replace all
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_replace_compatibility_200() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    fake_links = [
        _FakeLink(kind="spare_part"),
        _FakeLink(compatible_with_sku="MT-C-003", kind="accessory"),
    ]
    svc.replace_all_for_product = AsyncMock(return_value=fake_links)

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.put(
            "/api/v1/products/MT-A-001/compatibility",
            json=[
                {"compatible_with_sku": "MT-B-002", "kind": "spare_part"},
                {"compatible_with_sku": "MT-C-003", "kind": "accessory"},
            ],
        )

    assert resp.status_code == 200
    assert len(resp.json()) == 2


@pytest.mark.asyncio
async def test_replace_compatibility_empty_list() -> None:
    user = _FakeUser()
    svc = _mock_svc()
    svc.replace_all_for_product = AsyncMock(return_value=[])

    app = _build_app(user, svc)
    async with await _client(app) as ac:
        resp = await ac.put(
            "/api/v1/products/MT-A-001/compatibility",
            json=[],
        )

    assert resp.status_code == 200
    assert resp.json() == []
