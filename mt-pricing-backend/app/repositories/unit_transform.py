from __future__ import annotations

from sqlalchemy import select

from app.db.models.unit_transform import UnitTransform
from app.repositories.base import BaseRepository


class UnitTransformRepository(BaseRepository[UnitTransform]):
    model = UnitTransform
    pk_field = "id"
    soft_delete_field = None

    async def get_by_units(self, from_unit: str, to_unit: str) -> UnitTransform | None:
        stmt = select(UnitTransform).where(
            UnitTransform.from_unit == from_unit,
            UnitTransform.to_unit == to_unit,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self) -> list[UnitTransform]:
        stmt = select(UnitTransform).order_by(UnitTransform.from_unit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
