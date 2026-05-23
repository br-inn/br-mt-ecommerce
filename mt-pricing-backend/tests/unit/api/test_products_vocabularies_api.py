"""Unit tests for product vocabulary sub-resource endpoints (Wave 4).

Tests GET/POST/PUT/DELETE on /products/{sku}/certifications and /applications.
FastAPI ad-hoc app, no DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.vocabularies import (
    get_product_vocab_service,
    products_vocab_router,
)
from app.services.vocabularies.vocabulary_service import (
    ProductVocabularyService,
    VocabularyDomainError,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str] | None = None) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.deleted_at = None
        self.role = _FakeRole(perms or ["products:read", "products:write"])


def _make_cert_link(sku: str, cert_id: UUID | None = None) -> MagicMock:
    now = datetime.now(tz=UTC)
    link = MagicMock()
    link.product_sku = sku
    link.certification_id = cert_id or uuid4()
    link.certificate_pdf_asset_id = None
    link.obtained_at = None
    link.expires_at = None
    link.notes = None
    link.created_at = now
    cert = MagicMock()
    cert.code = "CE"
    cert.name = "CE Marking"
    cert.issued_by = "European Commission"
    cert.scope = "European conformity"
    cert.logo_url = None
    link.certification = cert
    return link


def _make_app_link(sku: str, app_id: UUID | None = None) -> MagicMock:
    now = datetime.now(tz=UTC)
    link = MagicMock()
    link.product_sku = sku
    link.application_id = app_id or uuid4()
    link.is_primary = False
    link.position = 0
    link.created_at = now
    app = MagicMock()
    app.code = "water"
    app.name = "Water"
    app.description = "Drinking water"
    link.application = app
    return link


def _build_app(
    user: _FakeUser,
    vocab_service: ProductVocabularyService,
) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(products_vocab_router, prefix="/api/v1/products")

    fake_session = MagicMock()

    async def _override_db():  # pragma: no cover
        yield fake_session

    def _override_user():
        return user

    test_app.dependency_overrides[get_db_session] = _override_db
    test_app.dependency_overrides[get_current_user] = _override_user
    test_app.dependency_overrides[get_product_vocab_service] = lambda: vocab_service
    return test_app


# ---------------------------------------------------------------------------
# Tests: Product certifications sub-resource
# ---------------------------------------------------------------------------
class TestProductCertificationsEndpoints:
    @pytest.mark.asyncio
    async def test_list_certifications_empty(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        svc.list_certifications = AsyncMock(return_value=[])

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/products/MT-V-001/certifications")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_certifications_returns_denormalized(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        cert_id = uuid4()
        link = _make_cert_link("MT-V-001", cert_id=cert_id)
        svc.list_certifications = AsyncMock(return_value=[link])

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/products/MT-V-001/certifications")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "CE"
        assert data[0]["certification_id"] == str(cert_id)

    @pytest.mark.asyncio
    async def test_add_certification_201(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        cert_id = uuid4()
        link = _make_cert_link("MT-V-001", cert_id=cert_id)
        svc.add_certification = AsyncMock(return_value=link)
        svc.list_certifications = AsyncMock(return_value=[link])

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/products/MT-V-001/certifications",
                json={"certification_id": str(cert_id)},
            )

        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_add_certification_invalid_cert_404(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        svc.add_certification = AsyncMock(
            side_effect=VocabularyDomainError("Cert not found", "certification_not_found", 404)
        )

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/products/MT-V-001/certifications",
                json={"certification_id": str(uuid4())},
            )

        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_replace_certifications_put(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        cert_id = uuid4()
        link = _make_cert_link("MT-V-001", cert_id=cert_id)
        svc.replace_certifications = AsyncMock(return_value=[link])
        svc.list_certifications = AsyncMock(return_value=[link])

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/products/MT-V-001/certifications",
                json=[{"certification_id": str(cert_id)}],
            )

        assert resp.status_code == 200
        assert len(resp.json()) == 1

    @pytest.mark.asyncio
    async def test_delete_certification_204(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        cert_id = uuid4()
        svc.remove_certification = AsyncMock(return_value=None)

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/products/MT-V-001/certifications/{cert_id}")

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_certification_not_linked_404(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        svc.remove_certification = AsyncMock(
            side_effect=VocabularyDomainError("Not linked", "product_certification_not_found", 404)
        )

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/products/MT-V-001/certifications/{uuid4()}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Product applications sub-resource
# ---------------------------------------------------------------------------
class TestProductApplicationsEndpoints:
    @pytest.mark.asyncio
    async def test_list_applications_empty(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        svc.list_applications = AsyncMock(return_value=[])

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/products/MT-V-001/applications")

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_list_applications_returns_denormalized(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        app_id = uuid4()
        link = _make_app_link("MT-V-001", app_id=app_id)
        svc.list_applications = AsyncMock(return_value=[link])

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/products/MT-V-001/applications")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "water"

    @pytest.mark.asyncio
    async def test_add_application_201(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        app_id = uuid4()
        link = _make_app_link("MT-V-001", app_id=app_id)
        svc.add_application = AsyncMock(return_value=link)
        svc.list_applications = AsyncMock(return_value=[link])

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/products/MT-V-001/applications",
                json={"application_id": str(app_id), "is_primary": True, "position": 0},
            )

        assert resp.status_code == 201

    @pytest.mark.asyncio
    async def test_replace_applications_put(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        app_id = uuid4()
        link = _make_app_link("MT-V-001", app_id=app_id)
        svc.replace_applications = AsyncMock(return_value=[link])
        svc.list_applications = AsyncMock(return_value=[link])

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.put(
                "/api/v1/products/MT-V-001/applications",
                json=[{"application_id": str(app_id), "is_primary": False, "position": 1}],
            )

        assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_delete_application_204(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        app_id = uuid4()
        svc.remove_application = AsyncMock(return_value=None)

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/products/MT-V-001/applications/{app_id}")

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_delete_application_not_linked_404(self) -> None:
        user = _FakeUser()
        svc = MagicMock(spec=ProductVocabularyService)
        svc.remove_application = AsyncMock(
            side_effect=VocabularyDomainError("Not linked", "product_application_not_found", 404)
        )

        test_app = _build_app(user, svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/products/MT-V-001/applications/{uuid4()}")

        assert resp.status_code == 404
