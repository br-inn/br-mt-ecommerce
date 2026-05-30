"""Repositorios async para el dominio pricing.

Convención: cada repo expone CRUD + métodos de búsqueda específicos. Sin commit
— la session es del caller (FastAPI dependency `get_db_session` hace
commit-on-success).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, desc, func, select

from app.db.models.currency import Currency
from app.db.models.pricing import (
    Channel,
    Cost,
    ExceptionRule,
    FXRate,
    Price,
    PriceApprovalEvent,
)
from app.repositories.base import BaseRepository


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------
class ChannelRepository(BaseRepository[Channel]):
    model = Channel
    soft_delete_field = None

    async def get_by_code(self, code: str) -> Channel | None:
        stmt = select(Channel).where(Channel.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_all(self, *, state: str | None = None) -> Sequence[Channel]:
        stmt = select(Channel)
        if state:
            stmt = stmt.where(Channel.state == state)
        stmt = stmt.order_by(Channel.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# FXRate
# ---------------------------------------------------------------------------
class FXRateRepository(BaseRepository[FXRate]):
    model = FXRate
    soft_delete_field = None

    async def get_active(
        self,
        from_currency: str,
        to_currency: str,
        as_of: datetime | None = None,
    ) -> FXRate | None:
        as_of = as_of or datetime.now(tz=UTC)
        stmt = (
            select(FXRate)
            .where(
                FXRate.from_currency == from_currency,
                FXRate.to_currency == to_currency,
                FXRate.effective_from <= as_of,
                (FXRate.effective_to.is_(None)) | (FXRate.effective_to > as_of),
            )
            .order_by(desc(FXRate.effective_from))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_pair(
        self, from_currency: str, to_currency: str, *, limit: int = 50
    ) -> Sequence[FXRate]:
        stmt = (
            select(FXRate)
            .where(
                FXRate.from_currency == from_currency,
                FXRate.to_currency == to_currency,
            )
            .order_by(desc(FXRate.effective_from))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_all(self, *, limit: int = 100) -> Sequence[FXRate]:
        stmt = select(FXRate).order_by(desc(FXRate.effective_from)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Cost
# ---------------------------------------------------------------------------
class CostRepository(BaseRepository[Cost]):
    """Repo del schema de costs con vigencia por rangos (mig 20260603_148).

    Las columnas reales son ``valid_from`` / ``valid_to`` (NULL = rango abierto).
    `effective_at` / `status` son hybrids derivados sólo de lectura. Para
    "coste vigente" filtramos por rango: ``valid_from <= as_of AND (valid_to IS
    NULL OR valid_to >= as_of)``.
    """

    model = Cost
    soft_delete_field = None

    async def get_active_for(
        self,
        product_sku: str,
        scheme_code: str,
        as_of: date | None = None,
    ) -> Cost | None:
        """Retorna el coste vigente a la fecha `as_of` (default hoy) para
        SKU+scheme. Vigente := ``valid_from <= as_of AND (valid_to IS NULL OR
        valid_to >= as_of)``. La exclusión GiST garantiza ≤1 fila.
        """
        on = as_of or date.today()
        stmt = (
            select(Cost)
            .where(
                Cost.sku == product_sku,
                Cost.scheme_code == scheme_code,
                Cost.valid_from <= on,
                (Cost.valid_to.is_(None)) | (Cost.valid_to >= on),
            )
            .order_by(desc(Cost.valid_from))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        product_sku: str | None = None,
        scheme_code: str | None = None,
        supplier_code: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
        include_total: bool = False,
    ) -> tuple[Sequence[Cost], UUID | None, int | None]:
        """Listado paginado (cursor por id ASC) con filtros opcionales."""
        clauses: list[Any] = []
        if product_sku:
            clauses.append(Cost.sku == product_sku)
        if scheme_code:
            clauses.append(Cost.scheme_code == scheme_code)
        if supplier_code:
            clauses.append(Cost.supplier_code == supplier_code)

        total: int | None = None
        if include_total:
            count_stmt = select(func.count()).select_from(Cost)
            if clauses:
                count_stmt = count_stmt.where(and_(*clauses))
            total_res = await self.session.execute(count_stmt)
            total = int(total_res.scalar_one() or 0)

        stmt = select(Cost)
        if cursor:
            clauses.append(Cost.id > cursor)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        stmt = stmt.order_by(Cost.id.asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        next_cursor: UUID | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].id
            rows = rows[:limit]
        return rows, next_cursor, total

    async def list_for_sku(
        self,
        product_sku: str,
        *,
        only_active: bool = False,
        as_of: date | None = None,
    ) -> Sequence[Cost]:
        """Devuelve los costos para un SKU (orden: scheme + valid_from desc).

        Si ``only_active`` filtra a los vigentes a la fecha ``as_of`` (default
        hoy): ``valid_from <= as_of AND (valid_to IS NULL OR valid_to >= as_of)``.
        """
        stmt = select(Cost).where(Cost.sku == product_sku)
        if only_active:
            on = as_of or date.today()
            stmt = stmt.where(
                Cost.valid_from <= on,
                (Cost.valid_to.is_(None)) | (Cost.valid_to >= on),
            )
        stmt = stmt.order_by(Cost.scheme_code.asc(), desc(Cost.valid_from))
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Price
# ---------------------------------------------------------------------------
class PriceRepository(BaseRepository[Price]):
    model = Price
    soft_delete_field = None

    async def get_active_for(
        self,
        product_sku: str,
        channel_id: UUID,
        scheme_code: str,
    ) -> Price | None:
        """Última propuesta activa (valid_to IS NULL) para SKU+channel+scheme."""
        stmt = (
            select(Price)
            .where(
                Price.product_sku == product_sku,
                Price.channel_id == channel_id,
                Price.scheme_code == scheme_code,
                Price.valid_to.is_(None),
            )
            .order_by(desc(Price.created_at))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        product_sku: str | None = None,
        channel_id: UUID | None = None,
        scheme_code: str | None = None,
        status: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
        include_total: bool = False,
    ) -> tuple[Sequence[Price], UUID | None, int | None]:
        clauses: list[Any] = []
        if product_sku:
            clauses.append(Price.product_sku == product_sku)
        if channel_id:
            clauses.append(Price.channel_id == channel_id)
        if scheme_code:
            clauses.append(Price.scheme_code == scheme_code)
        if status:
            clauses.append(Price.status == status)

        total: int | None = None
        if include_total:
            count_stmt = select(func.count()).select_from(Price)
            if clauses:
                count_stmt = count_stmt.where(and_(*clauses))
            total_res = await self.session.execute(count_stmt)
            total = int(total_res.scalar_one() or 0)

        stmt = select(Price)
        if cursor:
            clauses.append(Price.id > cursor)
        if clauses:
            stmt = stmt.where(and_(*clauses))
        stmt = stmt.order_by(Price.id.asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        next_cursor: UUID | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].id
            rows = rows[:limit]
        return rows, next_cursor, total

    async def list_pending_review(self, *, limit: int = 200) -> Sequence[Price]:
        stmt = (
            select(Price)
            .where(Price.status == "pending_review")
            .order_by(Price.created_at.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def supersede_previous(
        self,
        product_sku: str,
        channel_id: UUID,
        scheme_code: str,
        new_price_id: UUID,
    ) -> int:
        """Marca con valid_to=now() los precios activos previos (estados no terminales).

        Devuelve el número de filas afectadas.
        """
        now = datetime.now(tz=UTC)
        stmt = select(Price).where(
            Price.product_sku == product_sku,
            Price.channel_id == channel_id,
            Price.scheme_code == scheme_code,
            Price.valid_to.is_(None),
            Price.id != new_price_id,
        )
        result = await self.session.execute(stmt)
        affected = list(result.scalars().all())
        for p in affected:
            p.valid_to = now
        await self.session.flush()
        return len(affected)


# ---------------------------------------------------------------------------
# ExceptionRule
# ---------------------------------------------------------------------------
class ExceptionRuleRepository(BaseRepository[ExceptionRule]):
    model = ExceptionRule
    soft_delete_field = None

    async def list_active(self) -> Sequence[ExceptionRule]:
        stmt = select(ExceptionRule).where(ExceptionRule.active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def get_by_code(self, code: str) -> ExceptionRule | None:
        stmt = select(ExceptionRule).where(ExceptionRule.code == code)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create(self, data: dict) -> ExceptionRule:  # type: ignore[override]
        """Crea nueva regla de excepción (inactiva por defecto hasta activar)."""
        rule = ExceptionRule(**data)
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_by_id(self, rule_id: UUID) -> ExceptionRule | None:
        stmt = select(ExceptionRule).where(ExceptionRule.id == rule_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def activate(self, rule_id: UUID, actor_id: UUID) -> ExceptionRule:
        """Activa la regla `rule_id` y cierra la versión anterior activa del
        mismo scope (channel_id + scheme_code).

        Raises ValueError si `rule_id` no existe.
        """
        now = datetime.now(tz=UTC)

        rule = await self.get_by_id(rule_id)
        if rule is None:
            raise ValueError(f"ExceptionRule {rule_id} not found")

        # Cierra versiones previas activas del mismo scope (excluyendo la actual).
        stmt = select(ExceptionRule).where(
            ExceptionRule.active.is_(True),
            ExceptionRule.channel_id == rule.channel_id,
            ExceptionRule.scheme_code == rule.scheme_code,
            ExceptionRule.id != rule_id,
        )
        result = await self.session.execute(stmt)
        for prev in result.scalars().all():
            prev.active = False
            prev.effective_to = now

        # Activa la regla solicitada.
        rule.active = True
        rule.effective_from = now
        rule.effective_to = None
        await self.session.flush()
        return rule

    async def list_history(self, *, limit: int = 50) -> Sequence[ExceptionRule]:
        """Todas las reglas (activas e inactivas) ordenadas por created_at desc."""
        stmt = select(ExceptionRule).order_by(desc(ExceptionRule.created_at)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# PriceApprovalEvent
# ---------------------------------------------------------------------------
class PriceApprovalEventRepository(BaseRepository[PriceApprovalEvent]):
    model = PriceApprovalEvent
    soft_delete_field = None

    async def list_for_price(self, price_id: UUID) -> Sequence[PriceApprovalEvent]:
        stmt = (
            select(PriceApprovalEvent)
            .where(PriceApprovalEvent.price_id == price_id)
            .order_by(PriceApprovalEvent.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()


# ---------------------------------------------------------------------------
# Currency
# ---------------------------------------------------------------------------
class CurrencyRepository(BaseRepository[Currency]):
    """Read-only repo de currencies (Sprint 2 — solo seed)."""

    model = Currency
    pk_field = "code"
    soft_delete_field = None

    async def list_active(self) -> Sequence[Currency]:
        stmt = select(Currency).where(Currency.active.is_(True)).order_by(Currency.code.asc())
        result = await self.session.execute(stmt)
        return result.scalars().all()


__all__ = [
    "ChannelRepository",
    "CostRepository",
    "CurrencyRepository",
    "ExceptionRuleRepository",
    "FXRateRepository",
    "PriceApprovalEventRepository",
    "PriceRepository",
]


# Re-export Decimal helper for casual call-sites (price math).
__all__ += ["Decimal"]
