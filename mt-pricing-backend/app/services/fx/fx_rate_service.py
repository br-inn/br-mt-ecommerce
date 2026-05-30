"""FXRateService — create + list + audit (US-1A-05-03).

El cierre auto del rate previo + retroactive guard se delegan al trigger
PL/pgSQL ``fx_rates_close_previous_trg`` (migración 017). El servicio:

1. Valida currencies (FK).
2. Aplica defaults (`source='manual'`, identidad rate=1 si from==to).
3. Inserta vía repositorio. Si la BD lanza ``P0001`` con un mensaje
   ``error.code="fx_..."`` el servicio lo traduce a ``FXRateDomainError`` con
   status 422.
4. Emite ``fx_rate.created`` audit con before/after.

NO contiene lógica de cierre (eso es responsabilidad exclusiva del trigger);
el servicio sólo refresca el rate previo en memoria post-INSERT para la
respuesta del endpoint si el caller lo necesita.

Tests del trigger: ``tests/data/test_fx_rates_trigger.py`` (8+ casos).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError, InternalError, ProgrammingError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.currency import Currency
from app.db.models.pricing import FXRate
from app.db.models.user import User
from app.repositories.audit import AuditRepository


# ---------------------------------------------------------------------------
# Domain errors
# ---------------------------------------------------------------------------
class FXRateDomainError(Exception):
    """Errores de negocio recoverables — 4xx."""

    def __init__(self, code: str, message: str, status_code: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class InvalidFXCurrencyError(FXRateDomainError):
    def __init__(self, currency: str) -> None:
        super().__init__(
            code="fx_invalid_currency",
            message=(f"Moneda {currency!r} no existe o no está activa en `currencies`."),
            status_code=422,
        )


class FXRateRetroactiveBlockedError(FXRateDomainError):
    def __init__(self) -> None:
        super().__init__(
            code="fx_retroactive_not_allowed",
            message=(
                "El INSERT tiene `effective_from` < último rate vigente. "
                "Sólo TI/admin con `allow_retroactive=true` y reason puede forzarlo."
            ),
            status_code=422,
        )


class FXRateSameEffectiveFromError(FXRateDomainError):
    def __init__(self) -> None:
        super().__init__(
            code="fx_same_effective_from",
            message=(
                "Ya existe un rate con el mismo (from,to,effective_from) — no se "
                "permiten dos rates iniciando en el mismo instante."
            ),
            status_code=422,
        )


class FXRatePositiveError(FXRateDomainError):
    def __init__(self) -> None:
        super().__init__(
            code="fx_rate_must_be_positive",
            message="`rate` debe ser estrictamente > 0.",
            status_code=422,
        )


class FXRateNotFoundError(FXRateDomainError):
    def __init__(self, *, from_code: str, to_code: str, at: datetime) -> None:
        super().__init__(
            code="fx_rate_not_found_at_effective_at",
            message=(f"No existe rate vigente {from_code}→{to_code} a {at.isoformat()}."),
            status_code=422,
        )


# ---------------------------------------------------------------------------
# Trigger error mapping
# ---------------------------------------------------------------------------
_TRIGGER_ERROR_MAP: dict[str, type[FXRateDomainError]] = {
    "fx_retroactive_not_allowed": FXRateRetroactiveBlockedError,
    "fx_same_effective_from": FXRateSameEffectiveFromError,
    "fx_rate_must_be_positive": FXRatePositiveError,
}


def _translate_db_error(exc: Exception) -> FXRateDomainError | None:
    """Traduce un ``IntegrityError``/``InternalError`` del trigger a domain error.

    El trigger PL/pgSQL emite ``RAISE EXCEPTION`` con ``MESSAGE='fx_xxx'``
    (ver migración 017). asyncpg/psycopg lo expone en ``exc.orig.diag.message_primary``
    o en ``str(exc.orig)``.
    """
    msg = str(getattr(exc, "orig", exc))
    for trigger_code, err_cls in _TRIGGER_ERROR_MAP.items():
        if trigger_code in msg:
            return err_cls()
    return None


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------
def _snapshot(r: FXRate) -> dict[str, Any]:
    return {
        "from_currency": r.from_currency,
        "to_currency": r.to_currency,
        "rate": str(r.rate),
        "effective_from": r.effective_from.isoformat() if r.effective_from else None,
        "effective_to": r.effective_to.isoformat() if r.effective_to else None,
        "source": r.source,
    }


class FXRateService:
    """Crea + lista FX rates. Trigger maneja cierre auto + guard retroactivo."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.audit = AuditRepository(session)

    # ---------------------------------------------------------------- queries
    async def list_rates(
        self,
        *,
        from_code: str | None = None,
        to_code: str | None = None,
        only_active: bool = False,
        limit: int = 100,
    ) -> Sequence[FXRate]:
        stmt = select(FXRate)
        clauses = []
        if from_code:
            clauses.append(FXRate.from_currency == from_code.upper())
        if to_code:
            clauses.append(FXRate.to_currency == to_code.upper())
        if only_active:
            clauses.append(FXRate.effective_to.is_(None))
        if clauses:
            stmt = stmt.where(*clauses)
        stmt = stmt.order_by(desc(FXRate.effective_from)).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def rate_at(
        self,
        from_code: str,
        to_code: str,
        at: datetime,
    ) -> FXRate:
        """Devuelve el rate vigente para (from,to) a la fecha `at`.

        Identidad: si from==to, sintetiza un FXRate transitorio en memoria con
        rate=1 (el trigger fuerza la fila en BD pero también hay tests que
        consultan vía API antes de insertar la identidad).
        """
        from_code = from_code.upper()
        to_code = to_code.upper()
        if from_code == to_code:
            # Identity in-memory (no DB hit). Convención BR-1a-04.
            return FXRate(
                from_currency=from_code,
                to_currency=to_code,
                rate=Decimal("1"),
                effective_from=at,
                effective_to=None,
                source="identity",
            )

        stmt = (
            select(FXRate)
            .where(
                FXRate.from_currency == from_code,
                FXRate.to_currency == to_code,
                FXRate.effective_from <= at,
                (FXRate.effective_to.is_(None)) | (FXRate.effective_to > at),
            )
            .order_by(desc(FXRate.effective_from))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        row = result.scalar_one_or_none()
        if row is None:
            raise FXRateNotFoundError(from_code=from_code, to_code=to_code, at=at)
        return row

    # -------------------------------------------------------------- mutations
    async def create_rate(
        self,
        *,
        from_code: str,
        to_code: str,
        rate: Decimal | float | int | str,
        effective_from: datetime,
        source: str = "manual",
        actor: User | None,
        allow_retroactive: bool = False,
        reason: str | None = None,
    ) -> FXRate:
        from_code = from_code.upper()
        to_code = to_code.upper()
        rate_decimal = Decimal(str(rate))

        # Pre-flight: rate positivo (defensa antes de hacer round-trip a BD).
        if rate_decimal <= 0:
            raise FXRatePositiveError()

        # Identidad: forzamos rate=1 ANTES del INSERT (el trigger también lo
        # fuerza por defensa; tener ambos lados invariantes simplifica tests).
        if from_code == to_code:
            rate_decimal = Decimal("1")

        # Currencies activas (FK + business: no aceptar inactivas).
        await self._assert_currency_active(from_code)
        await self._assert_currency_active(to_code)

        # Importante: el flag `allow_retroactive` se mapea a un GUC
        # (`SET LOCAL fx.allow_retroactive='true'`) que el trigger lee en
        # tiempo de INSERT. Ámbito transaccional → no leakea entre requests.
        if allow_retroactive:
            if not reason:
                raise FXRateDomainError(
                    code="fx_retroactive_requires_reason",
                    message="`allow_retroactive=true` exige `reason` no vacío.",
                    status_code=422,
                )
            await self.session.execute(
                # Usamos parámetro vinculado dentro del SET LOCAL via plain text
                # — Postgres acepta SET LOCAL con literal sólo, así que
                # forzamos el literal 'true'.
                _set_local("fx.allow_retroactive", "true")
            )

        new_rate = FXRate(
            from_currency=from_code,
            to_currency=to_code,
            rate=rate_decimal,
            effective_from=effective_from,
            source=source,
        )
        # `created_by` se setea via attribute si la columna existe (migración 017).
        # Actor de sistema (job FX automático): actor=None → created_by NULL (F2).
        if hasattr(new_rate, "created_by"):
            new_rate.created_by = actor.id if actor is not None else None
        self.session.add(new_rate)

        try:
            await self.session.flush()
        except (IntegrityError, InternalError, ProgrammingError) as exc:
            translated = _translate_db_error(exc)
            if translated is not None:
                await self.session.rollback()
                raise translated from exc
            raise

        await self.audit.record(
            entity_type="fx_rate",
            entity_id=str(new_rate.id),
            action="fx_rate.created",
            actor_id=actor.id if actor is not None else None,
            actor_email=actor.email if actor is not None else None,
            actor_role=None if actor is not None else "system",
            after=_snapshot(new_rate),
            reason=reason,
        )
        return new_rate

    # ----------------------------------------------------------------- helpers
    async def _assert_currency_active(self, code: str) -> None:
        row = await self.session.get(Currency, code)
        if row is None or not row.active:
            raise InvalidFXCurrencyError(code)


# ---------------------------------------------------------------------------
# SET LOCAL helper — Postgres-only, plain text.
# ---------------------------------------------------------------------------
def _set_local(name: str, value: str) -> Any:
    """Construye un ``text()`` con ``SET LOCAL <name> = '<value>'``.

    Postgres NO acepta bind parameters en `SET LOCAL`. Forzamos un literal
    seguro: el `value` lo controla el servicio (literal 'true' por contrato).
    """
    from sqlalchemy import text

    if not value.replace("_", "").replace(".", "").isalnum():
        # Defensive: nuestro contrato sólo usa literales tipo 'true'/'false'.
        raise ValueError(f"SET LOCAL value inseguro: {value!r}")
    return text(f"SET LOCAL {name} = '{value}'")
