from __future__ import annotations

from sqlalchemy import select

from app.db.models.taxonomy_profile import TaxonomyProfile
from app.repositories.base import BaseRepository


class TaxonomyProfileRepository(BaseRepository[TaxonomyProfile]):
    model = TaxonomyProfile
    pk_field = "id"
    soft_delete_field = None

    async def get_by_family(self, family: str) -> TaxonomyProfile | None:
        stmt = select(TaxonomyProfile).where(TaxonomyProfile.family == family)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[TaxonomyProfile]:
        stmt = select(TaxonomyProfile).order_by(TaxonomyProfile.family)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert_by_family(
        self,
        family: str,
        weights: dict,
        hard_blockers: list[str],
        description: str | None = None,
    ) -> TaxonomyProfile:
        existing = await self.get_by_family(family)
        if existing:
            existing.weights = weights
            existing.hard_blockers = hard_blockers
            if description is not None:
                existing.description = description
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        return await self.create(
            family=family,
            weights=weights,
            hard_blockers=hard_blockers,
            description=description,
        )
