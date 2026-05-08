"""Unit tests for vocabulary catalog endpoints (Wave 4).

Tests GET/POST/PATCH/DELETE for certifications and applications catalog.
FastAPI ad-hoc app, no DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.vocabularies import (
    admin_vocab_router,
    get_app_service,
    get_cert_service,
    router as vocab_router,
)
from app.services.vocabularies.vocabulary_service import (
    ApplicationService,
    CertificationService,
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
        self.role = _FakeRole(perms or ["products:read", "products:write", "admin:vocabularies"])


def _make_cert_row(cert_id: UUID | None = None, code: str = "CE") -> MagicMock:
    row = MagicMock()
    row.id = cert_id or uuid4()
    row.code = code
    row.name = "CE Marking"
    row.issued_by = "European Commission"
    row.scope = "European conformity"
    row.logo_url = None
    row.active = True
    now = datetime.now(tz=UTC)
    row.created_at = now
    row.updated_at = now
    return row


def _make_app_row(app_id: UUID | None = None, code: str = "water") -> MagicMock:
    row = MagicMock()
    row.id = app_id or uuid4()
    row.code = code
    row.name = "Water"
    row.description = "Drinking water"
    row.active = True
    now = datetime.now(tz=UTC)
    row.created_at = now
    row.updated_at = now
    return row


def _build_app(
    user: _FakeUser,
    cert_service: CertificationService,
    app_service: ApplicationService,
) -> FastAPI:
    test_app = FastAPI()
    test_app.include_router(vocab_router, prefix="/api/v1")
    test_app.include_router(admin_vocab_router, prefix="/api/v1")

    fake_session = MagicMock()

    async def _override_db():  # pragma: no cover
        yield fake_session

    def _override_user():
        return user

    test_app.dependency_overrides[get_db_session] = _override_db
    test_app.dependency_overrides[get_current_user] = _override_user
    test_app.dependency_overrides[get_cert_service] = lambda: cert_service
    test_app.dependency_overrides[get_app_service] = lambda: app_service
    return test_app


# ---------------------------------------------------------------------------
# Tests: Public catalog reads
# ---------------------------------------------------------------------------
class TestPublicCatalogRead:
    @pytest.mark.asyncio
    async def test_list_certifications_returns_200(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        cert = _make_cert_row()
        cert_svc.list_active = AsyncMock(return_value=[cert])

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/certifications")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "CE"

    @pytest.mark.asyncio
    async def test_list_applications_returns_200(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        app_row = _make_app_row()
        app_svc.list_active = AsyncMock(return_value=[app_row])

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/applications")

        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["code"] == "water"


# ---------------------------------------------------------------------------
# Tests: Admin certifications CRUD
# ---------------------------------------------------------------------------
class TestAdminCertifications:
    @pytest.mark.asyncio
    async def test_admin_list_all_certifications(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        certs = [_make_cert_row(code="CE"), _make_cert_row(code="WRAS")]
        cert_svc.list_all = AsyncMock(return_value=certs)

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get("/api/v1/admin/certifications")

        assert resp.status_code == 200
        assert len(resp.json()) == 2

    @pytest.mark.asyncio
    async def test_admin_create_certification_201(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        cert = _make_cert_row()
        cert_svc.create = AsyncMock(return_value=cert)

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/admin/certifications",
                json={"code": "CE", "name": "CE Marking", "active": True},
            )

        assert resp.status_code == 201
        assert resp.json()["code"] == "CE"

    @pytest.mark.asyncio
    async def test_admin_create_certification_conflict_409(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        cert_svc.create = AsyncMock(
            side_effect=VocabularyDomainError(
                "Conflict", "certification_code_conflict", 409
            )
        )

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/admin/certifications",
                json={"code": "CE", "name": "CE Marking"},
            )

        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_admin_patch_certification(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        cert_id = uuid4()
        cert = _make_cert_row(cert_id=cert_id)
        cert.active = False
        cert_svc.patch = AsyncMock(return_value=cert)

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/api/v1/admin/certifications/{cert_id}",
                json={"active": False},
            )

        assert resp.status_code == 200
        assert resp.json()["active"] is False

    @pytest.mark.asyncio
    async def test_admin_delete_certification_204(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        cert_id = uuid4()
        cert_svc.delete = AsyncMock(return_value=None)

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/admin/certifications/{cert_id}")

        assert resp.status_code == 204

    @pytest.mark.asyncio
    async def test_admin_delete_certification_not_found_404(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        cert_svc.delete = AsyncMock(
            side_effect=VocabularyDomainError("Not found", "certification_not_found", 404)
        )

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.delete(f"/api/v1/admin/certifications/{uuid4()}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Admin applications CRUD
# ---------------------------------------------------------------------------
class TestAdminApplications:
    @pytest.mark.asyncio
    async def test_admin_create_application_201(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        app_row = _make_app_row()
        app_svc.create = AsyncMock(return_value=app_row)

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.post(
                "/api/v1/admin/applications",
                json={"code": "water", "name": "Water"},
            )

        assert resp.status_code == 201
        assert resp.json()["code"] == "water"

    @pytest.mark.asyncio
    async def test_admin_patch_application(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        app_id = uuid4()
        app_row = _make_app_row(app_id=app_id)
        app_row.description = "Updated description"
        app_svc.patch = AsyncMock(return_value=app_row)

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.patch(
                f"/api/v1/admin/applications/{app_id}",
                json={"description": "Updated description"},
            )

        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_admin_get_application_not_found(self) -> None:
        user = _FakeUser()
        cert_svc = MagicMock(spec=CertificationService)
        app_svc = MagicMock(spec=ApplicationService)
        app_svc.get_by_id = AsyncMock(
            side_effect=VocabularyDomainError("Not found", "application_not_found", 404)
        )

        test_app = _build_app(user, cert_svc, app_svc)
        async with AsyncClient(
            transport=ASGITransport(app=test_app), base_url="http://test"
        ) as client:
            resp = await client.get(f"/api/v1/admin/applications/{uuid4()}")

        assert resp.status_code == 404
