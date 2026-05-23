"""CRUD repository para CompetitorBrand + upsert de competitor_listings."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.comparator import CompetitorBrand, CompetitorListing
from app.services.matching.ports import CandidateRaw


class CompetitorBrandRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        name: str,
        *,
        amazon_search_term: str | None = None,
        amazon_dept: str = "industrial",
        amazon_category_node: str | None = None,
        is_active: bool = True,
        notes: str | None = None,
    ) -> CompetitorBrand:
        brand = CompetitorBrand(
            name=name,
            amazon_search_term=amazon_search_term,
            amazon_dept=amazon_dept,
            amazon_category_node=amazon_category_node,
            is_active=is_active,
            notes=notes,
        )
        self._session.add(brand)
        await self._session.flush()
        return brand

    async def get(self, brand_id: UUID) -> CompetitorBrand | None:
        return await self._session.get(CompetitorBrand, brand_id)

    async def get_by_name(self, name: str) -> CompetitorBrand | None:
        stmt = select(CompetitorBrand).where(func.lower(CompetitorBrand.name) == name.lower())
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_active(self) -> list[CompetitorBrand]:
        stmt = select(CompetitorBrand).where(CompetitorBrand.is_active.is_(True))
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[CompetitorBrand]:
        stmt = select(CompetitorBrand).order_by(CompetitorBrand.name)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def update(self, brand: CompetitorBrand, **kwargs: object) -> CompetitorBrand:
        for key, value in kwargs.items():
            setattr(brand, key, value)
        brand.updated_at = datetime.now(tz=UTC)
        await self._session.flush()
        return brand

    async def touch_scraped(self, brand: CompetitorBrand) -> None:
        brand.last_scraped_at = datetime.now(tz=UTC)
        brand.updated_at = datetime.now(tz=UTC)
        await self._session.flush()

    async def upsert_listing(
        self,
        candidate: CandidateRaw,
        *,
        competitor_brand_id: UUID,
    ) -> None:
        """Upsert un CandidateRaw en competitor_listings vinculado a la marca."""
        now = datetime.now(tz=UTC)
        image_url: str = candidate.raw_payload.get("image_url", "") or ""
        values = dict(
            source=candidate.source,
            source_id=candidate.external_id,
            source_url=candidate.raw_payload.get("url"),
            raw_payload_jsonb=candidate.raw_payload,
            normalized_jsonb={
                "title": candidate.title,
                "brand": candidate.brand,
                "price_aed": str(candidate.price_aed) if candidate.price_aed else None,
                "specs": candidate.specs,
            },
            image_url=image_url or None,
            competitor_brand_id=competitor_brand_id,
            last_seen_at=now,
        )
        excluded = pg_insert(CompetitorListing).excluded
        stmt = (
            pg_insert(CompetitorListing)
            .values(**values)
            .on_conflict_do_update(
                index_elements=["source", "source_id"],
                set_={
                    "raw_payload_jsonb": excluded.raw_payload_jsonb,
                    "normalized_jsonb": excluded.normalized_jsonb,
                    "image_url": excluded.image_url,
                    "competitor_brand_id": competitor_brand_id,
                    "last_seen_at": now,
                },
            )
        )
        await self._session.execute(stmt)
