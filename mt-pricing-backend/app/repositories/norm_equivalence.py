from __future__ import annotations

from sqlalchemy import select

from app.db.models.norm_equivalence import NormEquivalence
from app.repositories.base import BaseRepository


class NormEquivalenceRepository(BaseRepository[NormEquivalence]):
    model = NormEquivalence
    pk_field = "id"
    soft_delete_field = None

    async def list_all(self) -> list[NormEquivalence]:
        stmt = select(NormEquivalence).order_by(NormEquivalence.system_a, NormEquivalence.norm_a)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
