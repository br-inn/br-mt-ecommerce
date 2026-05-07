"""Repository para ``feature_flags`` (US-1A-09-08, Sprint 5).

Operaciones expuestas:
- :meth:`get_value` — devuelve bool del flag (default False).
- :meth:`upsert` — insert/update + audit columns.
- :meth:`list_all` — snapshot completo (admin endpoint).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.feature_flag import FeatureFlag


class FeatureFlagRepository:
    """Persistencia + audit sobre ``feature_flags``."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_value(self, key: str) -> bool:
        """Devuelve el valor booleano del flag — False si no existe."""
        stmt = select(FeatureFlag).where(FeatureFlag.key == key)
        row = (await self.session.execute(stmt)).scalar_one_or_none()
        if row is None:
            return False
        return bool(row.value_jsonb.get("enabled", False))

    async def get(self, key: str) -> FeatureFlag | None:
        stmt = select(FeatureFlag).where(FeatureFlag.key == key)
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_all(self) -> Sequence[FeatureFlag]:
        stmt = select(FeatureFlag).order_by(FeatureFlag.key)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def upsert(
        self,
        *,
        key: str,
        value: bool,
        updated_by: UUID | None = None,
    ) -> FeatureFlag:
        """Insert/update con audit. Devuelve el row final."""
        now = datetime.now(tz=UTC)
        payload: dict[str, Any] = {"enabled": bool(value)}

        stmt = pg_insert(FeatureFlag).values(
            key=key,
            value_jsonb=payload,
            updated_by=updated_by,
            updated_at=now,
            created_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[FeatureFlag.key],
            set_={
                "value_jsonb": payload,
                "updated_by": updated_by,
                "updated_at": now,
            },
        )
        await self.session.execute(stmt)
        await self.session.flush()

        row = await self.get(key)
        assert row is not None  # noqa: S101 — invariante post-upsert
        return row


__all__ = ["FeatureFlagRepository"]
