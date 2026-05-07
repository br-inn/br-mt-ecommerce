"""SupplierRepository — CRUD básico + listado paginado por `code` ASC.

Sigue patrón cursor-based de `ProductRepository`. Soft-delete via `active=false`
(no `deleted_at` en el modelo Supplier — la tabla no tiene esa columna en S2).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import and_, func, or_, select

from app.db.models.supplier import Supplier
from app.repositories.base import BaseRepository


class SupplierRepository(BaseRepository[Supplier]):
    model = Supplier
    pk_field = "code"
    soft_delete_field = None  # tabla `suppliers` no tiene `deleted_at`

    async def get_by_code(self, code: str) -> Supplier | None:
        return await self.get(code)

    async def list_paginated(
        self,
        *,
        active: bool | None = None,
        contract_currency: str | None = None,
        search: str | None = None,
        cursor: str | None = None,
        limit: int = 50,
        include_total: bool = False,
    ) -> tuple[Sequence[Supplier], str | None, int | None]:
        clauses: list[Any] = []
        if active is not None:
            clauses.append(Supplier.active.is_(active))
        if contract_currency is not None:
            clauses.append(Supplier.contract_currency == contract_currency.upper())
        if search:
            term = f"%{search}%"
            clauses.append(
                or_(Supplier.code.ilike(term), Supplier.name.ilike(term))
            )

        total: int | None = None
        if include_total:
            count_stmt = select(func.count()).select_from(Supplier)
            if clauses:
                count_stmt = count_stmt.where(and_(*clauses))
            res = await self.session.execute(count_stmt)
            total = int(res.scalar_one() or 0)

        stmt = select(Supplier)
        if cursor:
            clauses.append(Supplier.code > cursor)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        stmt = stmt.order_by(Supplier.code.asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        next_cursor: str | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].code
            rows = rows[:limit]
        return rows, next_cursor, total
