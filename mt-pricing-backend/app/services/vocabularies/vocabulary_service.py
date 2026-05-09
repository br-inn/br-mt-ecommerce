"""Vocabulary services — admin-curated catalog management + product linking.

- CertificationService, ApplicationService: CRUD vocabulary M:N.
- ProductVocabularyService: linking products to vocabulary entries.
- BrandService, FamilyService, SubfamilyService, ProductTypeService: taxonomy CRUD.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.vocabularies import (
    Application,
    Brand,
    Certification,
    Division,
    Family,
    Material,
    ProductApplication,
    ProductCertification,
    ProductDivision,
    ProductType,
    Series,
    SeriesCertification,
    SeriesDivision,
    SeriesTier,
    SeriesTranslation,
    Subfamily,
)
from app.repositories.vocabularies import (
    ApplicationRepo,
    BrandRepo,
    CertificationRepo,
    DivisionRepo,
    FamilyRepo,
    MaterialRepo,
    ProductApplicationRepo,
    ProductCertificationRepo,
    ProductDivisionRepo,
    ProductTypeRepo,
    SeriesCertificationRepo,
    SeriesDivisionRepo,
    SeriesRepo,
    SeriesTierRepo,
    SeriesTranslationRepo,
    SubfamilyRepo,
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


# ---------------------------------------------------------------------------
# Stage 1 Opción C — Taxonomía services
# ---------------------------------------------------------------------------


class BrandService:
    """Admin catalog management for brands."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = BrandRepo(session)

    async def list_active(self) -> Sequence[Brand]:
        return await self.repo.list_active()

    async def list_all(self) -> Sequence[Brand]:
        return await self.repo.list_all()

    async def get_by_id(self, brand_id: UUID) -> Brand:
        row = await self.repo.get(brand_id)
        if row is None:
            raise VocabularyDomainError(
                f"Brand {brand_id} not found",
                code="brand_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Brand:
        if await self.repo.get_by_code(data["code"]) is not None:
            raise VocabularyDomainError(
                f"Brand with code '{data['code']}' already exists",
                code="brand_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, brand_id: UUID, data: dict[str, Any]) -> Brand:
        row = await self.get_by_id(brand_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, brand_id: UUID) -> None:
        await self.get_by_id(brand_id)
        await self.repo.delete(brand_id)
        await self.session.commit()


class FamilyService:
    """Admin catalog management for families + tree query."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = FamilyRepo(session)

    async def list_active(self) -> Sequence[Family]:
        return await self.repo.list_active()

    async def list_all(self) -> Sequence[Family]:
        return await self.repo.list_all()

    async def list_tree(self) -> Sequence[Family]:
        return await self.repo.list_tree()

    async def get_by_id(self, family_id: UUID) -> Family:
        row = await self.repo.get(family_id)
        if row is None:
            raise VocabularyDomainError(
                f"Family {family_id} not found",
                code="family_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Family:
        if await self.repo.get_by_code(data["code"]) is not None:
            raise VocabularyDomainError(
                f"Family with code '{data['code']}' already exists",
                code="family_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, family_id: UUID, data: dict[str, Any]) -> Family:
        row = await self.get_by_id(family_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, family_id: UUID) -> None:
        await self.get_by_id(family_id)
        await self.repo.delete(family_id)
        await self.session.commit()


class SubfamilyService:
    """Admin catalog management for subfamilies (child of family)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SubfamilyRepo(session)
        self.family_repo = FamilyRepo(session)

    async def list_by_family(self, family_id: UUID) -> Sequence[Subfamily]:
        return await self.repo.list_by_family(family_id)

    async def list_all(self) -> Sequence[Subfamily]:
        return await self.repo.list_all()

    async def get_by_id(self, subfamily_id: UUID) -> Subfamily:
        row = await self.repo.get(subfamily_id)
        if row is None:
            raise VocabularyDomainError(
                f"Subfamily {subfamily_id} not found",
                code="subfamily_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Subfamily:
        family_id = data["family_id"]
        if await self.family_repo.get(family_id) is None:
            raise VocabularyDomainError(
                f"Family {family_id} not found",
                code="family_not_found",
                status_code=404,
            )
        existing = await self.repo.get_by_family_and_code(family_id, data["code"])
        if existing is not None:
            raise VocabularyDomainError(
                f"Subfamily with code '{data['code']}' already exists in family",
                code="subfamily_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, subfamily_id: UUID, data: dict[str, Any]) -> Subfamily:
        row = await self.get_by_id(subfamily_id)
        # family_id is immutable on patch — moving a subfamily across families
        # would require re-validating products that reference it.
        data.pop("family_id", None)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, subfamily_id: UUID) -> None:
        await self.get_by_id(subfamily_id)
        await self.repo.delete(subfamily_id)
        await self.session.commit()


class ProductTypeService:
    """Admin catalog management for product types (child of subfamily)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProductTypeRepo(session)
        self.subfamily_repo = SubfamilyRepo(session)

    async def list_by_subfamily(
        self, subfamily_id: UUID
    ) -> Sequence[ProductType]:
        return await self.repo.list_by_subfamily(subfamily_id)

    async def list_all(self) -> Sequence[ProductType]:
        return await self.repo.list_all()

    async def get_by_id(self, type_id: UUID) -> ProductType:
        row = await self.repo.get(type_id)
        if row is None:
            raise VocabularyDomainError(
                f"ProductType {type_id} not found",
                code="product_type_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> ProductType:
        subfamily_id = data["subfamily_id"]
        if await self.subfamily_repo.get(subfamily_id) is None:
            raise VocabularyDomainError(
                f"Subfamily {subfamily_id} not found",
                code="subfamily_not_found",
                status_code=404,
            )
        existing = await self.repo.get_by_subfamily_and_code(
            subfamily_id, data["code"]
        )
        if existing is not None:
            raise VocabularyDomainError(
                f"ProductType with code '{data['code']}' already exists in subfamily",
                code="product_type_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, type_id: UUID, data: dict[str, Any]) -> ProductType:
        row = await self.get_by_id(type_id)
        data.pop("subfamily_id", None)  # immutable
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, type_id: UUID) -> None:
        await self.get_by_id(type_id)
        await self.repo.delete(type_id)
        await self.session.commit()


# ---------------------------------------------------------------------------
# Stage 3 — Division (M:N) services
# ---------------------------------------------------------------------------


class DivisionService:
    """Admin CRUD para divisiones de catálogo (Hidrosanitario, Industrial, …)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DivisionRepo(session)

    async def list_active(self) -> Sequence[Division]:
        return await self.repo.list_active()

    async def list_all(self) -> Sequence[Division]:
        return await self.repo.list_all()

    async def get_by_id(self, division_id: UUID) -> Division:
        row = await self.repo.get(division_id)
        if row is None:
            raise VocabularyDomainError(
                f"Division {division_id} not found",
                code="division_not_found",
                status_code=404,
            )
        return row

    async def get_by_code(self, code: str) -> Division:
        row = await self.repo.get_by_code(code)
        if row is None:
            raise VocabularyDomainError(
                f"Division with code '{code}' not found",
                code="division_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Division:
        if await self.repo.get_by_code(data["code"]):
            raise VocabularyDomainError(
                f"Division code '{data['code']}' already exists",
                code="division_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, division_id: UUID, data: dict[str, Any]) -> Division:
        row = await self.get_by_id(division_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, division_id: UUID) -> None:
        await self.get_by_id(division_id)
        await self.repo.delete(division_id)
        await self.session.commit()


class ProductDivisionService:
    """Linking products ↔ divisions (M:N)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = ProductDivisionRepo(session)
        self.div_repo = DivisionRepo(session)

    async def list_for_product(
        self, product_sku: str
    ) -> Sequence[ProductDivision]:
        return await self.repo.list_for_product(product_sku)

    async def add(
        self, product_sku: str, division_id: UUID
    ) -> ProductDivision:
        if await self.div_repo.get(division_id) is None:
            raise VocabularyDomainError(
                f"Division {division_id} not found",
                code="division_not_found",
                status_code=404,
            )
        row = await self.repo.link(product_sku, division_id)
        await self.session.commit()
        return row

    async def remove(self, product_sku: str, division_id: UUID) -> None:
        ok = await self.repo.unlink(product_sku, division_id)
        if not ok:
            raise VocabularyDomainError(
                "Link not found",
                code="link_not_found",
                status_code=404,
            )
        await self.session.commit()

    async def replace_all(
        self, product_sku: str, division_ids: list[UUID]
    ) -> Sequence[ProductDivision]:
        # Validate all divisions exist
        for div_id in division_ids:
            if await self.div_repo.get(div_id) is None:
                raise VocabularyDomainError(
                    f"Division {div_id} not found",
                    code="division_not_found",
                    status_code=404,
                )
        rows = await self.repo.replace_all(product_sku, division_ids)
        await self.session.commit()
        return rows


# ---------------------------------------------------------------------------
# Stage 3 — SeriesTier service (vocab cerrado)
# ---------------------------------------------------------------------------


class SeriesTierService:
    """CRUD para tiers de serie (PLATINUM, GOLD, SILVER, BRONZE, N/A)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SeriesTierRepo(session)

    async def list_active(self) -> Sequence[SeriesTier]:
        return await self.repo.list_active()

    async def list_all(self) -> Sequence[SeriesTier]:
        return await self.repo.list_all()

    async def get_by_id(self, tier_id: UUID) -> SeriesTier:
        row = await self.repo.get(tier_id)
        if row is None:
            raise VocabularyDomainError(
                f"SeriesTier {tier_id} not found",
                code="series_tier_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> SeriesTier:
        if await self.repo.get_by_code(data["code"]):
            raise VocabularyDomainError(
                f"SeriesTier code '{data['code']}' already exists",
                code="series_tier_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, tier_id: UUID, data: dict[str, Any]) -> SeriesTier:
        row = await self.get_by_id(tier_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, tier_id: UUID) -> None:
        await self.get_by_id(tier_id)
        await self.repo.delete(tier_id)
        await self.session.commit()


# ---------------------------------------------------------------------------
# Stage 3 — Series (rica) service
# ---------------------------------------------------------------------------


class SeriesService:
    """CRUD para series + gestión de translations + junctions."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = SeriesRepo(session)
        self.tier_repo = SeriesTierRepo(session)
        self.tr_repo = SeriesTranslationRepo(session)
        self.div_repo = SeriesDivisionRepo(session)
        self.cert_repo = SeriesCertificationRepo(session)

    async def list_active(self) -> Sequence[Series]:
        return await self.repo.list_active()

    async def list_all(self) -> Sequence[Series]:
        return await self.repo.list_all()

    async def list_by_division(
        self, division_id: UUID
    ) -> Sequence[Series]:
        return await self.repo.list_by_division(division_id)

    async def get_by_id(self, series_id: UUID) -> Series:
        row = await self.repo.get(series_id)
        if row is None:
            raise VocabularyDomainError(
                f"Series {series_id} not found",
                code="series_not_found",
                status_code=404,
            )
        return row

    async def get_with_relations(self, series_id: UUID) -> Series:
        row = await self.repo.get_with_relations(series_id)
        if row is None:
            raise VocabularyDomainError(
                f"Series {series_id} not found",
                code="series_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Series:
        if await self.repo.get_by_code(data["code"]):
            raise VocabularyDomainError(
                f"Series code '{data['code']}' already exists",
                code="series_code_conflict",
                status_code=409,
            )
        if data.get("tier_id") is not None:
            if await self.tier_repo.get(data["tier_id"]) is None:
                raise VocabularyDomainError(
                    f"SeriesTier {data['tier_id']} not found",
                    code="series_tier_not_found",
                    status_code=404,
                )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(self, series_id: UUID, data: dict[str, Any]) -> Series:
        row = await self.get_by_id(series_id)
        if data.get("tier_id") is not None:
            if await self.tier_repo.get(data["tier_id"]) is None:
                raise VocabularyDomainError(
                    f"SeriesTier {data['tier_id']} not found",
                    code="series_tier_not_found",
                    status_code=404,
                )
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, series_id: UUID) -> None:
        await self.get_by_id(series_id)
        await self.repo.delete(series_id)
        await self.session.commit()

    # ---- Translations ----
    async def upsert_translation(
        self,
        series_id: UUID,
        lang: str,
        *,
        name: str,
        description: str | None,
        bullets: list[str],
    ) -> SeriesTranslation:
        await self.get_by_id(series_id)
        row = await self.tr_repo.upsert(
            series_id, lang, name=name, description=description, bullets=bullets
        )
        await self.session.commit()
        return row

    async def list_translations(
        self, series_id: UUID
    ) -> Sequence[SeriesTranslation]:
        await self.get_by_id(series_id)
        return await self.tr_repo.list_for_series(series_id)

    async def delete_translation(self, series_id: UUID, lang: str) -> None:
        await self.get_by_id(series_id)
        ok = await self.tr_repo.delete(series_id, lang)
        if not ok:
            raise VocabularyDomainError(
                f"Translation {lang} not found",
                code="translation_not_found",
                status_code=404,
            )
        await self.session.commit()

    # ---- Series ↔ Division (M:N) ----
    async def add_division(
        self, series_id: UUID, division_id: UUID
    ) -> SeriesDivision:
        await self.get_by_id(series_id)
        row = await self.div_repo.link(series_id, division_id)
        await self.session.commit()
        return row

    async def remove_division(
        self, series_id: UUID, division_id: UUID
    ) -> None:
        await self.get_by_id(series_id)
        ok = await self.div_repo.unlink(series_id, division_id)
        if not ok:
            raise VocabularyDomainError(
                "Link not found",
                code="link_not_found",
                status_code=404,
            )
        await self.session.commit()

    async def list_divisions(
        self, series_id: UUID
    ) -> Sequence[SeriesDivision]:
        await self.get_by_id(series_id)
        return await self.div_repo.list_for_series(series_id)

    # ---- Series ↔ Certification (M:N default) ----
    async def add_certification(
        self, series_id: UUID, certification_id: UUID
    ) -> SeriesCertification:
        await self.get_by_id(series_id)
        row = await self.cert_repo.link(series_id, certification_id)
        await self.session.commit()
        return row

    async def remove_certification(
        self, series_id: UUID, certification_id: UUID
    ) -> None:
        await self.get_by_id(series_id)
        ok = await self.cert_repo.unlink(series_id, certification_id)
        if not ok:
            raise VocabularyDomainError(
                "Link not found",
                code="link_not_found",
                status_code=404,
            )
        await self.session.commit()

    async def list_certifications(
        self, series_id: UUID
    ) -> Sequence[SeriesCertification]:
        await self.get_by_id(series_id)
        return await self.cert_repo.list_for_series(series_id)


# ---------------------------------------------------------------------------
# Stage 3 — Material service (vocab)
# ---------------------------------------------------------------------------


class MaterialService:
    """CRUD para vocabulario material."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = MaterialRepo(session)

    async def list_active(self) -> Sequence[Material]:
        return await self.repo.list_active()

    async def list_all(self) -> Sequence[Material]:
        return await self.repo.list_all()

    async def get_by_id(self, material_id: UUID) -> Material:
        row = await self.repo.get(material_id)
        if row is None:
            raise VocabularyDomainError(
                f"Material {material_id} not found",
                code="material_not_found",
                status_code=404,
            )
        return row

    async def create(self, data: dict[str, Any]) -> Material:
        if await self.repo.get_by_code(data["code"]):
            raise VocabularyDomainError(
                f"Material code '{data['code']}' already exists",
                code="material_code_conflict",
                status_code=409,
            )
        row = await self.repo.create(**data)
        await self.session.commit()
        return row

    async def patch(
        self, material_id: UUID, data: dict[str, Any]
    ) -> Material:
        row = await self.get_by_id(material_id)
        for k, v in data.items():
            setattr(row, k, v)
        await self.session.flush()
        await self.session.commit()
        return row

    async def delete(self, material_id: UUID) -> None:
        await self.get_by_id(material_id)
        await self.repo.delete(material_id)
        await self.session.commit()
