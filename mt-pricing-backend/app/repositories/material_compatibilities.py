"""Repository async para `material_compatibilities` (US-1A-06-03).

Operaciones:
- ``replace_all(rows)`` — TRUNCATE + INSERT (modo idempotente del importer).
- ``insert_many(rows)`` — bulk INSERT.
- ``find_by_descriptor(descriptor)`` — para el matching pipeline (S3).

NO commitea — la session es del caller (FastAPI dependency
``get_db_session`` hace commit-on-success).
"""

from __future__ import annotations

from collections.abc import Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.material_compatibility import MaterialCompatibility


class MaterialCompatibilitiesRepository:
    """Repo simple — no hereda BaseRepository porque la lógica de bulk replace
    no encaja con el contrato genérico (PK UUID server-side)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def replace_all(self, rows: Sequence[dict[str, Any]]) -> int:
        """TRUNCATE + INSERT atómico (en la misma transacción)."""
        await self.session.execute(delete(MaterialCompatibility))
        if not rows:
            return 0
        await self.session.execute(
            insert(MaterialCompatibility), [self._coerce_row(r) for r in rows]
        )
        return len(rows)

    async def insert_many(self, rows: Sequence[dict[str, Any]]) -> int:
        if not rows:
            return 0
        await self.session.execute(
            insert(MaterialCompatibility), [self._coerce_row(r) for r in rows]
        )
        return len(rows)

    async def find_by_descriptor(
        self, descriptor: str
    ) -> list[MaterialCompatibility]:
        stmt = (
            select(MaterialCompatibility)
            .where(MaterialCompatibility.producto_descriptor == descriptor)
            .order_by(MaterialCompatibility.temperatura_c.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        from sqlalchemy import func

        result = await self.session.execute(
            select(func.count()).select_from(MaterialCompatibility)
        )
        return int(result.scalar_one())

    @staticmethod
    def _coerce_row(r: dict[str, Any]) -> dict[str, Any]:
        out = dict(r)
        if isinstance(out.get("temperatura_c"), (int, float)):
            out["temperatura_c"] = Decimal(str(out["temperatura_c"]))
        return out
