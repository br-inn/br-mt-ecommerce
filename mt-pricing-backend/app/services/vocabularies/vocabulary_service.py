"""Vocabulary services — admin-curated catalog management + product linking.

- CertificationService: CRUD para el catálogo de certificaciones.
- ApplicationService: CRUD para el catálogo de aplicaciones.
- ProductVocabularyService: linking products to vocabulary entries.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vocabularies import Application, Certification, ProductApplication, ProductCertification
from app.repositories.vocabularies import (
    ApplicationRepo,
    CertificationRepo,
    ProductApplicationRepo,
    ProductCertificationRepo,
)


class VocabularyDomainError(Exception):
    """Base domain error for vocabulary operations."""

    def __init__(self, message: str, code: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code


class CertificationService:
    """Admin-only catalog management for certifications."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = CertificationRepo(session)

    async def list_active(self) -> Sequence[Certification]:
        return await self.repo.list_active()

    async def list_all(self) -> Sequence[Certification]:
        return await self.repo.list_all()

    async def get_by_id(self, cert_id: UUID) -> Certification:
        row = await self.repo.get(cert_id)
        if row is None:
            raise VocabularyDomainError(
                f"Certification {cert_id} not found",
                code="certification_not_found",
                status_code=404,
            )
        return row

    async def get_by_code(self, code: str) -> Certification:
        row = await self.repo.get_by_code(code)
        if row is None:
            raise VocabularyDomainError(
                f"Certification with code '{code}' not found",
                code="certification_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Certification:
        # Check unique code
        existing = await self.repo.get_by_code(data["code"])
        if existing is not None:
            raise VocabularyDomainError(
                f"Certification with code '{data['code']}' already exists",
                code="certification_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, cert_id: UUID, data: dict[str, Any]) -> Certification:
        row = await self.get_by_id(cert_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, cert_id: UUID) -> None:
        await self.get_by_id(cert_id)
        await self.repo.delete(cert_id)
        await self.session.commit()


class ApplicationService:
    """Admin-only catalog management for applications."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ApplicationRepo(session)

    async def list_active(self) -> Sequence[Application]:
        return await self.repo.list_active()

    async def list_all(self) -> Sequence[Application]:
        return await self.repo.list_all()

    async def get_by_id(self, app_id: UUID) -> Application:
        row = await self.repo.get(app_id)
        if row is None:
            raise VocabularyDomainError(
                f"Application {app_id} not found",
                code="application_not_found",
                status_code=404,
            )
        return row

    async def get_by_code(self, code: str) -> Application:
        row = await self.repo.get_by_code(code)
        if row is None:
            raise VocabularyDomainError(
                f"Application with code '{code}' not found",
                code="application_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Application:
        existing = await self.repo.get_by_code(data["code"])
        if existing is not None:
            raise VocabularyDomainError(
                f"Application with code '{data['code']}' already exists",
                code="application_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, app_id: UUID, data: dict[str, Any]) -> Application:
        row = await self.get_by_id(app_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, app_id: UUID) -> None:
        await self.get_by_id(app_id)
        await self.repo.delete(app_id)
        await self.session.commit()


class ProductVocabularyService:
    """Linking products to vocabulary entries (certifications + applications)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.cert_repo = ProductCertificationRepo(session)
        self.app_repo = ProductApplicationRepo(session)
        self._cert_catalog = CertificationRepo(session)
        self._app_catalog = ApplicationRepo(session)

    # ------------------------------------------------------------------
    # Certifications
    # ------------------------------------------------------------------
    async def list_certifications(self, product_sku: str) -> Sequence[ProductCertification]:
        return await self.cert_repo.list_for_product(product_sku)

    async def add_certification(
        self,
        product_sku: str,
        certification_id: UUID,
        **kwargs: Any,
    ) -> ProductCertification:
        # Validate cert exists
        cert = await self._cert_catalog.get(certification_id)
        if cert is None:
            raise VocabularyDomainError(
                f"Certification {certification_id} not found",
                code="certification_not_found",
                status_code=404,
            )
        row = await self.cert_repo.link(product_sku, certification_id, **kwargs)
        await self.session.commit()
        return row

    async def replace_certifications(
        self, product_sku: str, links: list[dict[str, Any]]
    ) -> Sequence[ProductCertification]:
        # Validate all cert IDs
        for lnk in links:
            cert = await self._cert_catalog.get(lnk["certification_id"])
            if cert is None:
                raise VocabularyDomainError(
                    f"Certification {lnk['certification_id']} not found",
                    code="certification_not_found",
                    status_code=404,
                )
        rows = await self.cert_repo.replace_all(product_sku, links)
        await self.session.commit()
        return rows

    async def remove_certification(
        self, product_sku: str, certification_id: UUID
    ) -> None:
        removed = await self.cert_repo.unlink(product_sku, certification_id)
        if not removed:
            raise VocabularyDomainError(
                f"Link product={product_sku} cert={certification_id} not found",
                code="product_certification_not_found",
                status_code=404,
            )
        await self.session.commit()

    # ------------------------------------------------------------------
    # Applications
    # ------------------------------------------------------------------
    async def list_applications(self, product_sku: str) -> Sequence[ProductApplication]:
        return await self.app_repo.list_for_product(product_sku)

    async def add_application(
        self,
        product_sku: str,
        application_id: UUID,
        *,
        is_primary: bool = False,
        position: int = 0,
    ) -> ProductApplication:
        app = await self._app_catalog.get(application_id)
        if app is None:
            raise VocabularyDomainError(
                f"Application {application_id} not found",
                code="application_not_found",
                status_code=404,
            )
        row = await self.app_repo.link(
            product_sku, application_id, is_primary=is_primary, position=position
        )
        await self.session.commit()
        return row

    async def replace_applications(
        self, product_sku: str, links: list[dict[str, Any]]
    ) -> Sequence[ProductApplication]:
        for lnk in links:
            app = await self._app_catalog.get(lnk["application_id"])
            if app is None:
                raise VocabularyDomainError(
                    f"Application {lnk['application_id']} not found",
                    code="application_not_found",
                    status_code=404,
                )
        rows = await self.app_repo.replace_all(product_sku, links)
        await self.session.commit()
        return rows

    async def remove_application(
        self, product_sku: str, application_id: UUID
    ) -> None:
        removed = await self.app_repo.unlink(product_sku, application_id)
        if not removed:
            raise VocabularyDomainError(
                f"Link product={product_sku} app={application_id} not found",
                code="product_application_not_found",
                status_code=404,
            )
        await self.session.commit()
