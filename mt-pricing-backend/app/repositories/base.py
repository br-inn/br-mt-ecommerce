"""BaseRepository genérico async.

Implementa CRUD simple sobre PK UUID. Repos concretos heredan y añaden
métodos de búsqueda específicos.

NO commitea — la session es responsabilidad del caller (FastAPI dependency
`get_db_session` hace commit-on-success).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar
from uuid import UUID

from sqlalchemy import inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """CRUD genérico sobre un modelo con PK simple.

    Subclases deben definir `model: type[ModelT]` y opcionalmente
    `pk_field` si la PK no se llama `id` (ej. Product usa `sku`).
    """

    model: type[ModelT]
    pk_field: str = "id"
    soft_delete_field: str | None = "deleted_at"

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ---------- helpers internos ----------
    def _pk_col(self) -> Any:
        return getattr(self.model, self.pk_field)

    def _has_soft_delete(self) -> bool:
        return (
            self.soft_delete_field is not None
            and self.soft_delete_field in inspect(self.model).columns.keys()  # noqa: SIM118
        )

    # ---------- CRUD ----------
    async def get(self, pk: UUID | str) -> ModelT | None:
        stmt = select(self.model).where(self._pk_col() == pk)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list(
        self,
        *,
        limit: int = 50,
        cursor: UUID | str | None = None,
        include_deleted: bool = False,
    ) -> tuple[Sequence[ModelT], UUID | str | None]:
        """Cursor-based pagination ordenada por PK ASC.

        Devuelve `(rows, next_cursor)`. `next_cursor` es el PK del último
        elemento si hay más resultados, `None` si la página fue la última.
        """
        stmt = select(self.model)
        if cursor is not None:
            stmt = stmt.where(self._pk_col() > cursor)
        if not include_deleted and self._has_soft_delete():
            stmt = stmt.where(getattr(self.model, self.soft_delete_field).is_(None))  # type: ignore[arg-type]
        stmt = stmt.order_by(self._pk_col().asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > limit:
            tail = rows[limit - 1]
            return rows[:limit], getattr(tail, self.pk_field)
        return rows, None

    async def create(self, **kwargs: Any) -> ModelT:
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()  # asigna PK server-side
        return obj

    async def update(self, pk: UUID | str, **kwargs: Any) -> ModelT | None:
        obj = await self.get(pk)
        if obj is None:
            return None
        for k, v in kwargs.items():
            setattr(obj, k, v)
        await self.session.flush()
        return obj

    async def delete(self, pk: UUID | str) -> bool:
        """Hard delete — usar con cuidado."""
        obj = await self.get(pk)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.flush()
        return True

    async def soft_delete(self, pk: UUID | str) -> bool:
        if not self._has_soft_delete():
            raise NotImplementedError(
                f"{self.model.__name__} no tiene `{self.soft_delete_field}` — usar delete()."
            )
        obj = await self.get(pk)
        if obj is None:
            return False
        setattr(obj, self.soft_delete_field, datetime.now(tz=timezone.utc))  # type: ignore[arg-type]
        await self.session.flush()
        return True
