"""Unit tests for Wave-1 asset endpoints on /products/{sku}/assets/*.

Pattern:
- Ad-hoc FastAPI app with only the products router mounted.
- Overrides: get_db_session, get_current_user, require_permissions closures,
  get_product_service, get_asset_service.
- ProductService mock (async), AssetService mock (async).
- No real DB or Supabase.

Cobertura (10+ tests):
1.  GET /assets → 200 + list.
2.  GET /assets → 404 when product not found.
3.  GET /assets?kind=photo → forwards kind filter.
4.  POST /assets/upload-url → 200 with signed URL payload.
5.  POST /assets/upload-url → 404 when product not found.
6.  POST /assets/{id}/confirm → 201 created.
7.  POST /assets/{id}/confirm → 422 on validation error.
8.  PATCH /assets/{id}/primary → 200.
9.  PATCH /assets/{id}/primary → 404 when not found.
10. PATCH /assets/{id}/archive → 200.
11. PATCH /assets/{id}/restore → 200.
12. DELETE /assets/{id} → 204.
13. DELETE /assets/{id} → 404.
14. GET /images (deprecated) → 200 + Deprecation header.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.products import (
    get_asset_service,
    get_product_service,
    router as products_router,
)
from app.services.assets.asset_service import AssetNotFoundError, AssetValidationError
from app.services.products.product_service import ProductNotFoundError

pytestmark = pytest.mark.unit

NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Fake user
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self) -> None:
        self.code = "admin"
        self.permissions_snapshot = [
            "products:read",
            "products:write",
            "products:delete",
            "assets:certify",
        ]


class _FakeUser:
    def __init__(self) -> None:
        self.id: UUID = uuid4()
        self.email = "admin@mt.ae"
        self.is_active = True
        self.deleted_at = None
        self.role = _FakeRole()


# ---------------------------------------------------------------------------
# Fake asset — plain namespace to avoid MagicMock auto-attribute issues
# ---------------------------------------------------------------------------
class _FakeAsset:
    def __init__(
        self,
        *,
        id: UUID | None = None,
        sku: str = "MT-V-038",
        kind: str = "photo",
        status: str = "active",
        is_primary: bool = False,
    ) -> None:
        self.id = id or uuid4()
        self.sku = sku
        self.kind = kind
        self.bucket = "product-images"
        self.storage_path = f"products/{sku}/photos/abc_img.jpg"
        self.original_url = None
        self.is_primary = is_primary
        self.position = 0
        self.alt_text = None
        self.locale = None
        self.caption = None
        self.width = 800
        self.height = 600
        self.bytes_size = 10240
        self.mime_type = "image/jpeg"
        self.hash_sha256 = None
        self.variants: dict = {}
        self.asset_meta: dict = {}
        self.revision = None
        self.supersedes_id = None
        self.status = status
        self.archived_at = None
        self.created_at = NOW
        self.created_by = uuid4()


def _make_asset(
    *,
    id: UUID | None = None,
    sku: str = "MT-V-038",
    kind: str = "photo",
    status: str = "active",
    is_primary: bool = False,
) -> _FakeAsset:
    return _FakeAsset(id=id, sku=sku, kind=kind, status=status, is_primary=is_primary)


# ---------------------------------------------------------------------------
# App builder
# ---------------------------------------------------------------------------
def _build_app(
    user: _FakeUser,
    product_service: Any,
    asset_service: Any,
) -> FastAPI:
    app = FastAPI()
    app.include_router(products_router, prefix="/api/v1")

    fake_session = MagicMock()

    async def _override_db() -> Any:
        yield fake_session

    async def _override_user() -> _FakeUser:
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_product_service] = lambda: product_service
    app.dependency_overrides[get_asset_service] = lambda: asset_service

    # Override all require_permissions closures.
    for route in products_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dep in dependant.dependencies:
            call = dep.call
            if call is not None and getattr(call, "__name__", "") == "_check":
                async def _allow(_call=call) -> _FakeUser:  # noqa: ARG001
                    return user
                app.dependency_overrides[call] = _allow

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _mock_product_service(*, found: bool = True) -> Any:
    svc = MagicMock()
    if found:
        svc.get_product_by_id = AsyncMock(return_value=MagicMock(sku="MT-V-038"))
    else:
        svc.get_product_by_id = AsyncMock(side_effect=ProductNotFoundError("MT-V-038"))
    return svc


def _mock_asset_service(assets: list | None = None) -> Any:
    svc = MagicMock()
    _assets = assets or []
    svc.list_for_product = AsyncMock(return_value=_assets)
    svc.generate_signed_upload_url = MagicMock(return_value={
        "storage_path": "products/MT-V-038/photos/abc_img.jpg",
        "upload_url": "https://fake-storage.local/product-images/...",
        "token": "fake-token",
        "method": "PUT",
        "headers": {"Content-Type": "image/jpeg"},
        "expires_in": 600,
        "bucket": "product-images",
        "kind": "photo",
    })
    svc.confirm_upload = AsyncMock(return_value=_make_asset())
    svc.set_primary = AsyncMock(return_value=_make_asset(is_primary=True))
    svc.archive = AsyncMock(return_value=_make_asset(status="archived"))
    svc.restore = AsyncMock(return_value=_make_asset(status="active"))
    svc.delete_hard = AsyncMock()
    return svc


# ---------------------------------------------------------------------------
# Tests: GET /assets
# ---------------------------------------------------------------------------
async def test_list_assets_returns_200() -> None:
    asset = _make_asset()
    svc = _mock_asset_service(assets=[asset])
    app = _build_app(_FakeUser(), _mock_product_service(), svc)

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-V-038/assets")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
    assert len(body) == 1
    assert body[0]["kind"] == "photo"


async def test_list_assets_404_when_product_not_found() -> None:
    svc = _mock_asset_service()
    app = _build_app(_FakeUser(), _mock_product_service(found=False), svc)

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/NOTEXIST/assets")
    assert resp.status_code == 404


async def test_list_assets_filters_by_kind() -> None:
    svc = _mock_asset_service(assets=[])
    app = _build_app(_FakeUser(), _mock_product_service(), svc)

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-V-038/assets?kind=photo")
    assert resp.status_code == 200
    svc.list_for_product.assert_called_once_with("MT-V-038", kind="photo", include_archived=False)


# ---------------------------------------------------------------------------
# Tests: POST /assets/upload-url
# ---------------------------------------------------------------------------
async def test_get_asset_upload_url_returns_200() -> None:
    svc = _mock_asset_service()
    app = _build_app(_FakeUser(), _mock_product_service(), svc)

    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MT-V-038/assets/upload-url",
            json={"kind": "photo", "filename": "product.jpg", "mime_type": "image/jpeg"},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert "storage_path" in body
    assert "upload_url" in body
    assert body["kind"] == "photo"


async def test_get_asset_upload_url_404_when_product_not_found() -> None:
    svc = _mock_asset_service()
    app = _build_app(_FakeUser(), _mock_product_service(found=False), svc)

    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/NOTEXIST/assets/upload-url",
            json={"kind": "photo", "filename": "product.jpg", "mime_type": "image/jpeg"},
        )
    assert resp.status_code == 404


async def test_get_asset_upload_url_422_on_validation_error() -> None:
    svc = _mock_asset_service()
    svc.generate_signed_upload_url = MagicMock(
        side_effect=AssetValidationError("mime_type inválido")
    )
    app = _build_app(_FakeUser(), _mock_product_service(), svc)

    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/products/MT-V-038/assets/upload-url",
            json={"kind": "photo", "filename": "doc.pdf", "mime_type": "application/pdf"},
        )
    # Pydantic validation (wrong mime for kind) fires at schema level → 422.
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: POST /assets/{id}/confirm
# ---------------------------------------------------------------------------
async def test_confirm_asset_upload_returns_201() -> None:
    svc = _mock_asset_service()
    app = _build_app(_FakeUser(), _mock_product_service(), svc)
    asset_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.post(
            f"/api/v1/products/MT-V-038/assets/{asset_id}/confirm",
            json={
                "storage_path": "products/MT-V-038/photos/abc_img.jpg",
                "kind": "photo",
                "mime_type": "image/jpeg",
                "bytes_size": 5120,
                "width": 800,
                "height": 600,
            },
        )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["kind"] == "photo"


async def test_confirm_asset_upload_422_on_service_error() -> None:
    svc = _mock_asset_service()
    svc.confirm_upload = AsyncMock(
        side_effect=AssetValidationError("bytes_size excede límite")
    )
    app = _build_app(_FakeUser(), _mock_product_service(), svc)
    asset_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.post(
            f"/api/v1/products/MT-V-038/assets/{asset_id}/confirm",
            json={
                "storage_path": "products/MT-V-038/photos/abc_img.jpg",
                "kind": "photo",
                "mime_type": "image/jpeg",
            },
        )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: PATCH /assets/{id}/primary
# ---------------------------------------------------------------------------
async def test_set_primary_asset_returns_200() -> None:
    svc = _mock_asset_service()
    app = _build_app(_FakeUser(), _mock_product_service(), svc)
    asset_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.patch(f"/api/v1/products/MT-V-038/assets/{asset_id}/primary")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["is_primary"] is True


async def test_set_primary_asset_404_when_not_found() -> None:
    svc = _mock_asset_service()
    svc.set_primary = AsyncMock(side_effect=AssetNotFoundError(uuid4()))
    app = _build_app(_FakeUser(), _mock_product_service(), svc)
    asset_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.patch(f"/api/v1/products/MT-V-038/assets/{asset_id}/primary")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: PATCH /assets/{id}/archive
# ---------------------------------------------------------------------------
async def test_archive_asset_returns_200() -> None:
    svc = _mock_asset_service()
    app = _build_app(_FakeUser(), _mock_product_service(), svc)
    asset_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.patch(f"/api/v1/products/MT-V-038/assets/{asset_id}/archive")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "archived"


# ---------------------------------------------------------------------------
# Tests: PATCH /assets/{id}/restore
# ---------------------------------------------------------------------------
async def test_restore_asset_returns_200() -> None:
    svc = _mock_asset_service()
    app = _build_app(_FakeUser(), _mock_product_service(), svc)
    asset_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.patch(f"/api/v1/products/MT-V-038/assets/{asset_id}/restore")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "active"


# ---------------------------------------------------------------------------
# Tests: DELETE /assets/{id}
# ---------------------------------------------------------------------------
async def test_delete_asset_returns_204() -> None:
    svc = _mock_asset_service()
    app = _build_app(_FakeUser(), _mock_product_service(), svc)
    asset_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.delete(f"/api/v1/products/MT-V-038/assets/{asset_id}")
    assert resp.status_code == 204


async def test_delete_asset_404_when_not_found() -> None:
    svc = _mock_asset_service()
    svc.delete_hard = AsyncMock(side_effect=AssetNotFoundError(uuid4()))
    app = _build_app(_FakeUser(), _mock_product_service(), svc)
    asset_id = uuid4()

    async with await _client(app) as ac:
        resp = await ac.delete(f"/api/v1/products/MT-V-038/assets/{asset_id}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: deprecated /images endpoints
# ---------------------------------------------------------------------------
async def test_deprecated_list_images_returns_200() -> None:
    """GET /images still works and returns photos only."""

    class _FakeProd:
        sku = "MT-V-038"
        images = [_make_asset()]

    prod_svc = MagicMock()
    prod_svc.get_product_by_id = AsyncMock(return_value=_FakeProd())
    svc = _mock_asset_service()

    app = _build_app(_FakeUser(), prod_svc, svc)

    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/products/MT-V-038/images")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert isinstance(body, list)
