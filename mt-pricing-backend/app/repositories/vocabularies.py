"""Repositories — vocabularios curados.

- Wave 4: Certification, Application + product link repos
- Stage 1 Opción C: Brand, Family, Subfamily, ProductType (taxonomía)

Repos concretos sin commit — la session del caller lo maneja.
"""

from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

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
            select(Application).where(Application.active.is_(True)).order_by(Application.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Application]:
        stmt = select(Application).order_by(Application.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ProductCertificationRepo:
    """Repository for product ↔ certification links."""

    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:  # type: ignore[name-defined]
        self.session = session

    async def link(
        self,
        product_sku: str,
        certification_id: UUID,
        *,
        certificate_pdf_asset_id: UUID | None = None,
        obtained_at: date | None = None,  # type: ignore[name-defined]
        expires_at: date | None = None,  # type: ignore[name-defined]
        notes: str | None = None,
        owner_type: str = "product",
        owner_id: str | None = None,
    ) -> ProductCertification:
        """Create or update a product-certification link.

        Fase 5 — owner_type/owner_id polymorphic. Por compat layer, cuando
        ``owner_type='product'`` y owner_id es None, owner_id se autorrellena
        con product_sku.
        """
        if owner_id is None:
            owner_id = product_sku
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
            existing.owner_type = owner_type
            existing.owner_id = owner_id
            await self.session.flush()
            return existing

        row = ProductCertification(
            product_sku=product_sku,
            certification_id=certification_id,
            certificate_pdf_asset_id=certificate_pdf_asset_id,
            obtained_at=obtained_at,
            expires_at=expires_at,
            notes=notes,
            owner_type=owner_type,
            owner_id=owner_id,
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
        """Atomically replace all certifications for a product.

        Fase 5 — propaga owner_type/owner_id por item; default 'product'/product_sku.
        """
        # Delete existing
        await self.session.execute(
            delete(ProductCertification).where(ProductCertification.product_sku == product_sku)
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
                owner_type=lnk.get("owner_type", "product"),
                owner_id=lnk.get("owner_id") or product_sku,
            )
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        return rows


class ProductApplicationRepo:
    """Repository for product ↔ application links."""

    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:  # type: ignore[name-defined]
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

    async def get_link(self, product_sku: str, application_id: UUID) -> ProductApplication | None:
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
            delete(ProductApplication).where(ProductApplication.product_sku == product_sku)
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


# ---------------------------------------------------------------------------
# Stage 1 Opción C — Taxonomía
# ---------------------------------------------------------------------------


class BrandRepo(BaseRepository[Brand]):
    model = Brand
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Brand | None:
        stmt = select(Brand).where(Brand.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Brand]:
        stmt = select(Brand).where(Brand.active.is_(True)).order_by(Brand.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Brand]:
        stmt = select(Brand).order_by(Brand.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


class FamilyRepo(BaseRepository[Family]):
    model = Family
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Family | None:
        stmt = select(Family).where(Family.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Family]:
        stmt = (
            select(Family)
            .where(Family.active.is_(True))
            .order_by(Family.sort_order.asc(), Family.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Family]:
        stmt = select(Family).order_by(Family.sort_order.asc(), Family.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_tree(self) -> Sequence[Family]:
        """Carga families + subfamilies + product_types en una sola query."""
        stmt = (
            select(Family)
            .options(selectinload(Family.subfamilies).selectinload(Subfamily.product_types))
            .order_by(Family.sort_order.asc(), Family.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class SubfamilyRepo(BaseRepository[Subfamily]):
    model = Subfamily
    pk_field = "id"
    soft_delete_field = None

    async def get_by_family_and_code(self, family_id: UUID, code: str) -> Subfamily | None:
        stmt = select(Subfamily).where(Subfamily.family_id == family_id, Subfamily.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_family(self, family_id: UUID) -> Sequence[Subfamily]:
        stmt = (
            select(Subfamily)
            .where(Subfamily.family_id == family_id)
            .order_by(Subfamily.sort_order.asc(), Subfamily.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Subfamily]:
        stmt = select(Subfamily).order_by(
            Subfamily.family_id, Subfamily.sort_order.asc(), Subfamily.code.asc()
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ProductTypeRepo(BaseRepository[ProductType]):
    model = ProductType
    pk_field = "id"
    soft_delete_field = None

    async def get_by_subfamily_and_code(self, subfamily_id: UUID, code: str) -> ProductType | None:
        stmt = select(ProductType).where(
            ProductType.subfamily_id == subfamily_id, ProductType.code == code
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_subfamily(self, subfamily_id: UUID) -> Sequence[ProductType]:
        stmt = (
            select(ProductType)
            .where(ProductType.subfamily_id == subfamily_id)
            .order_by(ProductType.sort_order.asc(), ProductType.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[ProductType]:
        stmt = select(ProductType).order_by(
            ProductType.subfamily_id,
            ProductType.sort_order.asc(),
            ProductType.code.asc(),
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Stage 3 — Division + ProductDivision (M:N)
# ---------------------------------------------------------------------------


class DivisionRepo(BaseRepository[Division]):
    model = Division
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Division | None:
        stmt = select(Division).where(Division.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Division]:
        stmt = (
            select(Division)
            .where(Division.active.is_(True))
            .order_by(Division.sort_order.asc(), Division.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Division]:
        stmt = select(Division).order_by(Division.sort_order.asc(), Division.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


class ProductDivisionRepo:
    """Repository for product ↔ division links (M:N)."""

    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:  # type: ignore[name-defined]
        self.session = session

    async def link(self, product_sku: str, division_id: UUID) -> ProductDivision:
        existing = await self.get_link(product_sku, division_id)
        if existing:
            return existing
        row = ProductDivision(product_sku=product_sku, division_id=division_id)
        self.session.add(row)
        await self.session.flush()
        return row

    async def unlink(self, product_sku: str, division_id: UUID) -> bool:
        stmt = delete(ProductDivision).where(
            ProductDivision.product_sku == product_sku,
            ProductDivision.division_id == division_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def get_link(self, product_sku: str, division_id: UUID) -> ProductDivision | None:
        stmt = select(ProductDivision).where(
            ProductDivision.product_sku == product_sku,
            ProductDivision.division_id == division_id,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_product(self, product_sku: str) -> Sequence[ProductDivision]:
        stmt = (
            select(ProductDivision)
            .where(ProductDivision.product_sku == product_sku)
            .options(selectinload(ProductDivision.division))
            .order_by(ProductDivision.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def replace_all(
        self, product_sku: str, division_ids: list[UUID]
    ) -> Sequence[ProductDivision]:
        await self.session.execute(
            delete(ProductDivision).where(ProductDivision.product_sku == product_sku)
        )
        rows: list[ProductDivision] = []
        for div_id in division_ids:
            row = ProductDivision(product_sku=product_sku, division_id=div_id)
            self.session.add(row)
            rows.append(row)
        await self.session.flush()
        return rows


# ---------------------------------------------------------------------------
# Stage 3 — SeriesTier
# ---------------------------------------------------------------------------


class SeriesTierRepo(BaseRepository[SeriesTier]):
    model = SeriesTier
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> SeriesTier | None:
        stmt = select(SeriesTier).where(SeriesTier.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[SeriesTier]:
        stmt = (
            select(SeriesTier)
            .where(SeriesTier.active.is_(True))
            .order_by(SeriesTier.rank.asc(), SeriesTier.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[SeriesTier]:
        stmt = select(SeriesTier).order_by(SeriesTier.rank.asc(), SeriesTier.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Stage 3 — Series (rica) + translations + junctions
# ---------------------------------------------------------------------------


class SeriesRepo(BaseRepository[Series]):
    model = Series
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Series | None:
        stmt = select(Series).where(Series.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_relations(self, series_id: UUID) -> Series | None:
        stmt = (
            select(Series)
            .where(Series.id == series_id)
            .options(
                selectinload(Series.tier),
                selectinload(Series.translations),
                selectinload(Series.series_divisions).selectinload(SeriesDivision.division),
                selectinload(Series.series_certifications).selectinload(
                    SeriesCertification.certification
                ),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Series]:
        stmt = (
            select(Series)
            .where(Series.active.is_(True))
            .order_by(Series.sort_order.asc(), Series.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Series]:
        stmt = select(Series).order_by(Series.sort_order.asc(), Series.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_division(self, division_id: UUID) -> Sequence[Series]:
        stmt = (
            select(Series)
            .join(SeriesDivision, SeriesDivision.series_id == Series.id)
            .where(
                SeriesDivision.division_id == division_id,
                Series.active.is_(True),
            )
            .order_by(Series.sort_order.asc(), Series.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class SeriesTranslationRepo:
    """Repo de traducciones (upsert por (series_id, lang))."""

    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:  # type: ignore[name-defined]
        self.session = session

    async def upsert(
        self,
        series_id: UUID,
        lang: str,
        *,
        name: str,
        description: str | None,
        bullets: list[str],
    ) -> SeriesTranslation:
        existing = await self.get(series_id, lang)
        if existing:
            existing.name = name
            existing.description = description
            existing.bullets = bullets
            await self.session.flush()
            return existing
        row = SeriesTranslation(
            series_id=series_id,
            lang=lang,
            name=name,
            description=description,
            bullets=bullets,
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def get(self, series_id: UUID, lang: str) -> SeriesTranslation | None:
        stmt = select(SeriesTranslation).where(
            SeriesTranslation.series_id == series_id,
            SeriesTranslation.lang == lang,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_for_series(self, series_id: UUID) -> Sequence[SeriesTranslation]:
        stmt = (
            select(SeriesTranslation)
            .where(SeriesTranslation.series_id == series_id)
            .order_by(SeriesTranslation.lang.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def delete(self, series_id: UUID, lang: str) -> bool:
        stmt = delete(SeriesTranslation).where(
            SeriesTranslation.series_id == series_id,
            SeriesTranslation.lang == lang,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0


class SeriesDivisionRepo:
    """Junction series ↔ divisions."""

    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:  # type: ignore[name-defined]
        self.session = session

    async def link(self, series_id: UUID, division_id: UUID) -> SeriesDivision:
        stmt = select(SeriesDivision).where(
            SeriesDivision.series_id == series_id,
            SeriesDivision.division_id == division_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        row = SeriesDivision(series_id=series_id, division_id=division_id)
        self.session.add(row)
        await self.session.flush()
        return row

    async def unlink(self, series_id: UUID, division_id: UUID) -> bool:
        stmt = delete(SeriesDivision).where(
            SeriesDivision.series_id == series_id,
            SeriesDivision.division_id == division_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def list_for_series(self, series_id: UUID) -> Sequence[SeriesDivision]:
        stmt = (
            select(SeriesDivision)
            .where(SeriesDivision.series_id == series_id)
            .options(selectinload(SeriesDivision.division))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


class SeriesCertificationRepo:
    """Junction series ↔ certifications (paquete default)."""

    def __init__(self, session: sqlalchemy.ext.asyncio.AsyncSession) -> None:  # type: ignore[name-defined]
        self.session = session

    async def link(self, series_id: UUID, certification_id: UUID) -> SeriesCertification:
        stmt = select(SeriesCertification).where(
            SeriesCertification.series_id == series_id,
            SeriesCertification.certification_id == certification_id,
        )
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            return existing
        row = SeriesCertification(series_id=series_id, certification_id=certification_id)
        self.session.add(row)
        await self.session.flush()
        return row

    async def unlink(self, series_id: UUID, certification_id: UUID) -> bool:
        stmt = delete(SeriesCertification).where(
            SeriesCertification.series_id == series_id,
            SeriesCertification.certification_id == certification_id,
        )
        result = await self.session.execute(stmt)
        return result.rowcount > 0

    async def list_for_series(self, series_id: UUID) -> Sequence[SeriesCertification]:
        stmt = (
            select(SeriesCertification)
            .where(SeriesCertification.series_id == series_id)
            .options(selectinload(SeriesCertification.certification))
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Stage 3 — Material
# ---------------------------------------------------------------------------


class MaterialRepo(BaseRepository[Material]):
    model = Material
    pk_field = "id"
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Material | None:
        stmt = select(Material).where(Material.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> Sequence[Material]:
        stmt = (
            select(Material)
            .where(Material.active.is_(True))
            .order_by(Material.sort_order.asc(), Material.code.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self) -> Sequence[Material]:
        stmt = select(Material).order_by(Material.sort_order.asc(), Material.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()
