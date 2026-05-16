from __future__ import annotations

from typing import Any

from sqlalchemy import select

from app.db.models.comparator_config import ComparatorConfig
from app.repositories.base import BaseRepository


class ComparatorConfigRepository(BaseRepository[ComparatorConfig]):
    model = ComparatorConfig
    pk_field = "id"
    soft_delete_field = None

    async def get_value(self, key: str, default: Any = None) -> Any:
        stmt = select(ComparatorConfig.value).where(ComparatorConfig.key == key)
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        return row if row is not None else default

    async def set_value(
        self, key: str, value: Any, description: str | None = None
    ) -> ComparatorConfig:
        stmt = select(ComparatorConfig).where(ComparatorConfig.key == key)
        result = await self.session.execute(stmt)
        existing = result.scalar_one_or_none()
        if existing:
            existing.value = value
            await self.session.flush()
            return existing
        return await self.create(key=key, value=value, description=description)

    async def get_all(self) -> dict[str, Any]:
        stmt = select(ComparatorConfig)
        result = await self.session.execute(stmt)
        return {row.key: row.value for row in result.scalars().all()}
