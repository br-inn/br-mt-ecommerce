"""Unit tests for vocabulary services (Wave 4).

Tests CertificationService, ApplicationService, ProductVocabularyService.
All tests use in-memory fakes — no DB required.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest

from app.services.vocabularies.vocabulary_service import (
    ApplicationService,
    CertificationService,
    ProductVocabularyService,
    VocabularyDomainError,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
def _make_cert(
    cert_id: UUID | None = None,
    code: str = "CE",
    name: str = "CE Marking",
    active: bool = True,
) -> MagicMock:
    row = MagicMock()
    row.id = cert_id or uuid4()
    row.code = code
    row.name = name
    row.issued_by = "European Commission"
    row.scope = "European conformity"
    row.logo_url = None
    row.active = active
    row.created_at = datetime.now(tz=UTC)
    row.updated_at = datetime.now(tz=UTC)
    return row


def _make_app(
    app_id: UUID | None = None,
    code: str = "water",
    name: str = "Water",
    active: bool = True,
) -> MagicMock:
    row = MagicMock()
    row.id = app_id or uuid4()
    row.code = code
    row.name = name
    row.description = "Drinking water"
    row.active = active
    row.created_at = datetime.now(tz=UTC)
    row.updated_at = datetime.now(tz=UTC)
    return row


def _make_prod_cert(sku: str, cert_id: UUID) -> MagicMock:
    row = MagicMock()
    row.product_sku = sku
    row.certification_id = cert_id
    row.certificate_pdf_asset_id = None
    row.obtained_at = None
    row.expires_at = None
    row.notes = None
    row.created_at = datetime.now(tz=UTC)
    return row


def _make_prod_app(sku: str, app_id: UUID) -> MagicMock:
    row = MagicMock()
    row.product_sku = sku
    row.application_id = app_id
    row.is_primary = False
    row.position = 0
    row.created_at = datetime.now(tz=UTC)
    return row


# ---------------------------------------------------------------------------
# CertificationService tests
# ---------------------------------------------------------------------------
class TestCertificationService:
    def _build_service(self) -> tuple[CertificationService, MagicMock]:
        session = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        service = CertificationService(session)
        service.repo = MagicMock()
        return service, session

    @pytest.mark.asyncio
    async def test_list_active_returns_active_rows(self) -> None:
        service, _ = self._build_service()
        cert = _make_cert()
        service.repo.list_active = AsyncMock(return_value=[cert])

        result = await service.list_active()

        assert result == [cert]
        service.repo.list_active.assert_called_once()

    @pytest.mark.asyncio
    async def test_list_all_returns_all(self) -> None:
        service, _ = self._build_service()
        certs = [_make_cert(code="CE"), _make_cert(code="WRAS", active=False)]
        service.repo.list_all = AsyncMock(return_value=certs)

        result = await service.list_all()

        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_get_by_id_found(self) -> None:
        service, _ = self._build_service()
        cert = _make_cert()
        service.repo.get = AsyncMock(return_value=cert)

        result = await service.get_by_id(cert.id)

        assert result is cert

    @pytest.mark.asyncio
    async def test_get_by_id_not_found_raises_404(self) -> None:
        service, _ = self._build_service()
        service.repo.get = AsyncMock(return_value=None)

        with pytest.raises(VocabularyDomainError) as exc_info:
            await service.get_by_id(uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "certification_not_found"

    @pytest.mark.asyncio
    async def test_create_succeeds(self) -> None:
        service, session = self._build_service()
        cert = _make_cert()
        service.repo.get_by_code = AsyncMock(return_value=None)
        service.repo.create = AsyncMock(return_value=cert)

        result = await service.create({"code": "CE", "name": "CE Marking", "active": True})

        assert result is cert
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_conflict_raises_409(self) -> None:
        service, _ = self._build_service()
        existing = _make_cert()
        service.repo.get_by_code = AsyncMock(return_value=existing)

        with pytest.raises(VocabularyDomainError) as exc_info:
            await service.create({"code": "CE", "name": "CE Marking", "active": True})

        assert exc_info.value.status_code == 409
        assert exc_info.value.code == "certification_code_conflict"

    @pytest.mark.asyncio
    async def test_patch_updates_fields(self) -> None:
        service, session = self._build_service()
        cert = _make_cert()
        service.repo.get = AsyncMock(return_value=cert)
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        result = await service.patch(cert.id, {"name": "Updated Name"})

        assert cert.name == "Updated Name"
        assert result is cert

    @pytest.mark.asyncio
    async def test_delete_calls_repo(self) -> None:
        service, session = self._build_service()
        cert = _make_cert()
        service.repo.get = AsyncMock(return_value=cert)
        service.repo.delete = AsyncMock(return_value=True)

        await service.delete(cert.id)

        service.repo.delete.assert_called_once_with(cert.id)
        session.commit.assert_called_once()


# ---------------------------------------------------------------------------
# ApplicationService tests
# ---------------------------------------------------------------------------
class TestApplicationService:
    def _build_service(self) -> tuple[ApplicationService, MagicMock]:
        session = MagicMock()
        session.flush = AsyncMock()
        session.commit = AsyncMock()
        service = ApplicationService(session)
        service.repo = MagicMock()
        return service, session

    @pytest.mark.asyncio
    async def test_list_active(self) -> None:
        service, _ = self._build_service()
        apps = [_make_app()]
        service.repo.list_active = AsyncMock(return_value=apps)

        result = await service.list_active()

        assert result == apps

    @pytest.mark.asyncio
    async def test_get_by_code_found(self) -> None:
        service, _ = self._build_service()
        app = _make_app(code="water")
        service.repo.get_by_code = AsyncMock(return_value=app)

        result = await service.get_by_code("water")

        assert result.code == "water"

    @pytest.mark.asyncio
    async def test_get_by_code_not_found(self) -> None:
        service, _ = self._build_service()
        service.repo.get_by_code = AsyncMock(return_value=None)

        with pytest.raises(VocabularyDomainError) as exc_info:
            await service.get_by_code("nonexistent")

        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_create_application(self) -> None:
        service, session = self._build_service()
        app = _make_app()
        service.repo.get_by_code = AsyncMock(return_value=None)
        service.repo.create = AsyncMock(return_value=app)

        result = await service.create({"code": "water", "name": "Water", "active": True})

        assert result is app
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_patch_application(self) -> None:
        service, session = self._build_service()
        app = _make_app()
        service.repo.get = AsyncMock(return_value=app)
        session.flush = AsyncMock()
        session.commit = AsyncMock()

        result = await service.patch(app.id, {"active": False})

        assert app.active is False
        assert result is app


# ---------------------------------------------------------------------------
# ProductVocabularyService tests
# ---------------------------------------------------------------------------
class TestProductVocabularyService:
    def _build_service(self) -> tuple[ProductVocabularyService, MagicMock]:
        session = MagicMock()
        session.commit = AsyncMock()
        service = ProductVocabularyService(session)
        service.cert_repo = MagicMock()
        service.app_repo = MagicMock()
        service._cert_catalog = MagicMock()
        service._app_catalog = MagicMock()
        return service, session

    @pytest.mark.asyncio
    async def test_list_certifications(self) -> None:
        service, _ = self._build_service()
        cert_id = uuid4()
        link = _make_prod_cert("MT-V-001", cert_id)
        service.cert_repo.list_for_product = AsyncMock(return_value=[link])

        result = await service.list_certifications("MT-V-001")

        assert len(result) == 1
        assert result[0].certification_id == cert_id

    @pytest.mark.asyncio
    async def test_add_certification_invalid_cert_raises_404(self) -> None:
        service, _ = self._build_service()
        service._cert_catalog.get = AsyncMock(return_value=None)

        with pytest.raises(VocabularyDomainError) as exc_info:
            await service.add_certification("MT-V-001", uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "certification_not_found"

    @pytest.mark.asyncio
    async def test_add_certification_valid(self) -> None:
        service, session = self._build_service()
        cert = _make_cert()
        link = _make_prod_cert("MT-V-001", cert.id)
        service._cert_catalog.get = AsyncMock(return_value=cert)
        service.cert_repo.link = AsyncMock(return_value=link)

        result = await service.add_certification("MT-V-001", cert.id)

        assert result is link
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_replace_certifications(self) -> None:
        service, session = self._build_service()
        cert_id = uuid4()
        cert = _make_cert(cert_id=cert_id)
        service._cert_catalog.get = AsyncMock(return_value=cert)
        service.cert_repo.replace_all = AsyncMock(return_value=[])

        await service.replace_certifications("MT-V-001", [{"certification_id": cert_id}])

        service.cert_repo.replace_all.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_certification_not_linked_raises_404(self) -> None:
        service, _ = self._build_service()
        service.cert_repo.unlink = AsyncMock(return_value=False)

        with pytest.raises(VocabularyDomainError) as exc_info:
            await service.remove_certification("MT-V-001", uuid4())

        assert exc_info.value.status_code == 404
        assert "not found" in exc_info.value.message

    @pytest.mark.asyncio
    async def test_add_application_valid(self) -> None:
        service, session = self._build_service()
        app = _make_app()
        link = _make_prod_app("MT-V-001", app.id)
        service._app_catalog.get = AsyncMock(return_value=app)
        service.app_repo.link = AsyncMock(return_value=link)

        result = await service.add_application("MT-V-001", app.id, is_primary=True)

        assert result is link
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_application_invalid_app_raises_404(self) -> None:
        service, _ = self._build_service()
        service._app_catalog.get = AsyncMock(return_value=None)

        with pytest.raises(VocabularyDomainError) as exc_info:
            await service.add_application("MT-V-001", uuid4())

        assert exc_info.value.status_code == 404
        assert exc_info.value.code == "application_not_found"

    @pytest.mark.asyncio
    async def test_replace_applications(self) -> None:
        service, session = self._build_service()
        app_id = uuid4()
        app = _make_app(app_id=app_id)
        service._app_catalog.get = AsyncMock(return_value=app)
        service.app_repo.replace_all = AsyncMock(return_value=[])

        await service.replace_applications(
            "MT-V-001", [{"application_id": app_id, "is_primary": True, "position": 0}]
        )

        service.app_repo.replace_all.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_remove_application_not_linked_raises_404(self) -> None:
        service, _ = self._build_service()
        service.app_repo.unlink = AsyncMock(return_value=False)

        with pytest.raises(VocabularyDomainError) as exc_info:
            await service.remove_application("MT-V-001", uuid4())

        assert exc_info.value.status_code == 404
