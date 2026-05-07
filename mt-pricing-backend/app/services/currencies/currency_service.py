"""CurrencyService — admin activate/deactivate + audit (US-1A-05-01-S3).

Contrato:
- ``list_all`` devuelve TODAS las currencies (incl. inactivas) — el admin las
  necesita para reactivar.
- ``set_active`` aplica `active=true|false` con audit + diff. Falla si:
  - currency no existe (404 → ``currency_not_found``).
  - se intenta desactivar `is_base=true` (422 → ``cannot_deactivate_base_currency``).

NO permite crear/borrar currencies en S3 (riesgo: monedas sin FX rotos).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.currency import Currency
from app.db.models.user import User
from app.repositories.audit import AuditRepository


class CurrencyDomainError(Exception):
    """Errores de negocio recoverables — 4xx en routes."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class CurrencyNotFoundError(CurrencyDomainError):
    def __init__(self, code: str) -> None:
        super().__init__(
            code="currency_not_found",
            message=f"Moneda {code!r} no existe en `currencies`.",
            status_code=404,
        )


class CannotDeactivateBaseCurrencyError(CurrencyDomainError):
    def __init__(self, code: str) -> None:
        super().__init__(
            code="cannot_deactivate_base_currency",
            message=(
                f"No se puede desactivar la moneda base {code!r} (is_base=true). "
                "Cambia primero la base."
            ),
            status_code=422,
        )


_AUDIT_FIELDS = ("code", "name", "symbol", "decimals", "is_base", "active")


def _snapshot(c: Currency) -> dict[str, Any]:
    return {f: getattr(c, f) for f in _AUDIT_FIELDS}


class CurrencyService:
    """Admin activate/deactivate. Stateless por request."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditRepository(session)

    # ---------------------------------------------------------------- queries
    async def get_by_code(self, code: str) -> Currency:
        normalized = code.strip().upper()
        row = await self.session.get(Currency, normalized)
        if row is None:
            raise CurrencyNotFoundError(normalized)
        return row

    async def list_all(self, *, only_active: bool = False) -> Sequence[Currency]:
        stmt = select(Currency).order_by(Currency.code.asc())
        if only_active:
            stmt = stmt.where(Currency.active.is_(True))
        result = await self.session.execute(stmt)
        return result.scalars().all()

    # -------------------------------------------------------------- mutations
    async def set_active(
        self,
        code: str,
        *,
        active: bool,
        actor: User,
        reason: str | None = None,
    ) -> Currency:
        currency = await self.get_by_code(code)

        # Defense in depth — además del partial unique index sobre is_base,
        # bloqueamos a nivel servicio para devolver el código de error que
        # el AC exige.
        if not active and currency.is_base:
            raise CannotDeactivateBaseCurrencyError(currency.code)

        if currency.active is active:
            return currency  # Idempotente: no audit, no flush.

        before = _snapshot(currency)
        currency.active = active
        await self.session.flush()
        after = _snapshot(currency)

        await self.audit.record(
            entity_type="currency",
            entity_id=currency.code,
            action="currency.activated" if active else "currency.deactivated",
            actor_id=actor.id,
            actor_email=actor.email,
            before=before,
            after=after,
            payload_diff={"active": {"from": not active, "to": active}},
            reason=reason,
        )
        return currency
