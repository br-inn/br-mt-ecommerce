"""Repositories — Certification, Application, ProductCertification, ProductApplication.

Wave 4: vocabularios M:N. Repos concretos, sin commit — la session del caller lo maneja.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from app.db.models.vocabularies import (
    Application,
    Certification,
    ProductApplication,
    ProductCertification,
)
from app.repositories.base import BaseRepository


class CertificationRepo(BaseRepository[Certification]):
    model = Certification
    pk_field = "id"
    soft_delete_field = None  # catálogo no tiene soft-delete, usa active flag

    async def get_by_code(self, code: str) -> Certification | None:
        stmt = select(Certification).where(Certification.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Certification]:
        stmt = (
            select(Certification)
            .where(Certification.active.is_(True))
            .order_by(Certification.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Certification]:
        stmt = select(Certification).order_by(Certification.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ApplicationRepo(BaseRepository[Application]):
    model = Application
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Application | None:
        stmt = select(Application).where(Application.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Application]:
        stmt = (
            select(Application)
            .where(Application.active.is_(True))
            .order_by(Application.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Application]:
        stmt = select(Application).order_by(Application.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ProductCertificationRepo:
    """Repository for product ↔ certification links."""

    def __init__(self, session: "sqlalchemy.ext.asyncio.AsyncSession") -> None:  # type: ignore[name-defined]
        self.session = session

    async def link(
        self,
        product_sku: str,
        certification_id: UUID,
        *,
        certificate_pdf_asset_id: UUID | None = None,
        obtained_at: "date | None" = None,  # type: ignore[name-defined]
        expires_at: "date | None" = None,  # type: ignore[name-defined]
        notes: str | None = None,
    ) -> ProductCertification:
        """Create or update a product-certification link."""
        # Upsert pattern: try to get existing, update or create.
        existing = await self.get_link(product_sku, certification_id)
        if existing:
            if certificate_pdf_asset_id is not None:
                existing.certificate_pdf_asset_id = certificate_pdf_asset_id
            if obtained_at is not None:
                existing.obtained_at = obtained_at
            if expires_at is not None:
                existing.expires_at = expires_at
            if notes is not None:
                existing.notes = notes
            await self.session.flush()
            return existing

        row = ProductCertification(
            product_sku=product_sku,
            certification_id=certification_id,
            certificate_pdf_asset_id=certificate_pdf_asset_id,
            obtained_at=obtained_at,
            expires_at=expires_at,
            notes=notes,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def unlink(self, product_sku: str, certification_id: UUID) -> bool:
        stmt = delete(ProductCertification).where(
            ProductCertification.product_sku == product_sku,
            ProductCertification.certification_id == certification_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_link(
        self, product_sku: str, certification_id: UUID
    ) -> ProductCertification | None:
        stmt = select(ProductCertification).where(
            ProductCertification.product_sku == product_sku,
            ProductCertification.certification_id == certification_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_product(self, product_sku: str) -> Sequence[ProductCertification]:
        stmt = (
            select(ProductCertification)
            .where(ProductCertification.product_sku == product_sku)
            .options(selectinload(ProductCertification.certification))
            .order_by(ProductCertification.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def replace_all(
        self,
        product_sku: str,
        links: list[dict],
    ) -> Sequence[ProductCertification]:
        """Atomically replace all certifications for a product."""
        # Delete existing
        await self.session.execute(
            delete(ProductCertification).where(
                ProductCertification.product_sku == product_sku
            )
        )
        # Insert new ones
        rows: list[ProductCertification] = []
        for lnk in links:
            row = ProductCertification(
                product_sku=product_sku,
                certification_id=lnk["certification_id"],
                certificate_pdf_asset_id=lnk.get("certificate_pdf_asset_id"),
                obtained_at=lnk.get("obtained_at"),
                expires_at=lnk.get("expires_at"),
                notes=lnk.get("notes"),
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        return rows


class ProductApplicationRepo:
    """Repository for product ↔ application links."""

    def __init__(self, session: "sqlalchemy.ext.asyncio.AsyncSession") -> None:  # type: ignore[name-defined]
        self.session = session

    async def link(
        self,
        product_sku: str,
        application_id: UUID,
        *,
        is_primary: bool = False,
        position: int = 0,
    ) -> ProductApplication:
        """Create or update a product-application link."""
        existing = await self.get_link(product_sku, application_id)
        if existing:
            existing.is_primary = is_primary
            existing.position = position
            await self.session.flush()
            return existing

        row = ProductApplication(
            product_sku=product_sku,
            application_id=application_id,
            is_primary=is_primary,
            position=position,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def unlink(self, product_sku: str, application_id: UUID) -> bool:
        stmt = delete(ProductApplication).where(
            ProductApplication.product_sku == product_sku,
            ProductApplication.application_id == application_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_link(
        self, product_sku: str, application_id: UUID
    ) -> ProductApplication | None:
        stmt = select(ProductApplication).where(
            ProductApplication.product_sku == product_sku,
            ProductApplication.application_id == application_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_product(self, product_sku: str) -> Sequence[ProductApplication]:
        stmt = (
            select(ProductApplication)
            .where(ProductApplication.product_sku == product_sku)
            .options(selectinload(ProductApplication.application))
            .order_by(ProductApplication.position.asc(), ProductApplication.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def replace_all(
        self,
        product_sku: str,
        links: list[dict],
    ) -> Sequence[ProductApplication]:
        """Atomically replace all applications for a product."""
        await self.session.execute(
            delete(ProductApplication).where(
                ProductApplication.product_sku == product_sku
            )
        )
        rows: list[ProductApplication] = []
        for lnk in links:
            row = ProductApplication(
                product_sku=product_sku,
                application_id=lnk["application_id"],
                is_primary=lnk.get("is_primary", False),
                position=lnk.get("position", 0),
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        return rows
