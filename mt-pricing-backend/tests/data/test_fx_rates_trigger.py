"""Integration tests del trigger ``fx_rates_close_previous_trg`` y la función
``fx_rate_at`` (US-1A-05-02 — migración 017).

Estrategia: levantar Postgres efímero vía testcontainers + ``alembic upgrade head``
(idéntico patrón a ``tests/db/test_suppliers.py``). Cada test usa una transacción
aislada (``db_session`` rollback al final).

Cobertura BDD (8 casos):
1. Insert nuevo cierra el previo con ``effective_to = NEW.effective_from``.
2. Insert con ``effective_from`` < último vigente sin flag → ``fx_retroactive_not_allowed``.
3. Insert con mismo ``effective_from`` exacto → ``fx_same_effective_from``.
4. ``fx_rate_at`` devuelve la fila vigente para una fecha ``t`` dada (5.4 AC).
5. Insert AED→AED con rate=999 → trigger fuerza rate=1.
6. Insert con ``rate=0`` → trigger lanza ``fx_rate_must_be_positive``.
7. ``allow_retroactive`` flag (SET LOCAL) habilita inserts retroactivos.
8. Múltiples pares independientes: cerrar EUR→AED no afecta a USD→AED.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError, InternalError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    """``alembic upgrade head`` antes de los tests del módulo."""
    from alembic import command
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _purge_pair(
    session: "AsyncSession", from_c: str, to_c: str
) -> None:
    """Borra todas las filas del par (limpia entre tests dentro de la mismatx)."""
    await session.execute(
        text(
            "DELETE FROM fx_rates WHERE from_currency = :f AND to_currency = :t"
        ),
        {"f": from_c, "t": to_c},
    )


async def _insert_rate(
    session: "AsyncSession",
    *,
    from_c: str,
    to_c: str,
    rate: float | Decimal,
    effective_from: datetime,
    source: str = "manual",
) -> str:
    """INSERT plain text — no engagement con ORM (testea trigger directo).

    Devuelve el id de la fila insertada como string.
    """
    result = await session.execute(
        text(
            """
            INSERT INTO fx_rates (from_currency, to_currency, rate, effective_from, source)
            VALUES (:f, :t, :r, :ef, :s)
            RETURNING id
            """
        ),
        {
            "f": from_c,
            "t": to_c,
            "r": str(Decimal(str(rate))),
            "ef": effective_from,
            "s": source,
        },
    )
    return str(result.scalar_one())


async def _row_by_id(session: "AsyncSession", row_id: str) -> dict:
    res = await session.execute(
        text(
            """
            SELECT id, from_currency, to_currency, rate, effective_from, effective_to, source
              FROM fx_rates WHERE id = :id
            """
        ),
        {"id": row_id},
    )
    row = res.first()
    assert row is not None
    return dict(row._mapping)  # type: ignore[attr-defined]


# ---------------------------------------------------------------------------
# AC-1 — Insert nuevo cierra el previo
# ---------------------------------------------------------------------------
async def test_insert_closes_previous_active_rate(db_session: "AsyncSession") -> None:
    await _purge_pair(db_session, "EUR", "AED")
    prev_id = await _insert_rate(
        db_session,
        from_c="EUR",
        to_c="AED",
        rate=4.29,
        effective_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    new_at = datetime(2026, 6, 12, tzinfo=timezone.utc)
    new_id = await _insert_rate(
        db_session, from_c="EUR", to_c="AED", rate=4.18, effective_from=new_at
    )

    prev = await _row_by_id(db_session, prev_id)
    new = await _row_by_id(db_session, new_id)

    assert prev["effective_to"] == new_at
    assert new["effective_to"] is None
    assert Decimal(str(new["rate"])) == Decimal("4.18000000")


# ---------------------------------------------------------------------------
# AC-2 — Retroactivo sin flag → bloqueo
# ---------------------------------------------------------------------------
async def test_retroactive_insert_blocked_without_flag(
    db_session: "AsyncSession",
) -> None:
    await _purge_pair(db_session, "EUR", "AED")
    await _insert_rate(
        db_session,
        from_c="EUR",
        to_c="AED",
        rate=4.29,
        effective_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    with pytest.raises((IntegrityError, InternalError, Exception)) as ei:
        await _insert_rate(
            db_session,
            from_c="EUR",
            to_c="AED",
            rate=4.10,
            effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
    assert "fx_retroactive_not_allowed" in str(ei.value)


# ---------------------------------------------------------------------------
# AC-3 — Mismo effective_from → bloqueo
# ---------------------------------------------------------------------------
async def test_same_effective_from_blocked(db_session: "AsyncSession") -> None:
    await _purge_pair(db_session, "EUR", "AED")
    same_at = datetime(2026, 4, 1, tzinfo=timezone.utc)
    await _insert_rate(
        db_session, from_c="EUR", to_c="AED", rate=4.29, effective_from=same_at
    )
    with pytest.raises((IntegrityError, InternalError, Exception)) as ei:
        await _insert_rate(
            db_session,
            from_c="EUR",
            to_c="AED",
            rate=4.30,
            effective_from=same_at,
        )
    assert "fx_same_effective_from" in str(ei.value)


# ---------------------------------------------------------------------------
# AC-4 — fx_rate_at devuelve la fila vigente
# ---------------------------------------------------------------------------
async def test_fx_rate_at_returns_active_row(db_session: "AsyncSession") -> None:
    await _purge_pair(db_session, "EUR", "AED")
    apr_id = await _insert_rate(
        db_session,
        from_c="EUR",
        to_c="AED",
        rate=4.29,
        effective_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    jun_id = await _insert_rate(
        db_session,
        from_c="EUR",
        to_c="AED",
        rate=4.18,
        effective_from=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )

    res_apr = await db_session.execute(
        text("SELECT fx_rate_at('EUR','AED', :t) AS id"),
        {"t": datetime(2026, 5, 1, tzinfo=timezone.utc)},
    )
    res_jul = await db_session.execute(
        text("SELECT fx_rate_at('EUR','AED', :t) AS id"),
        {"t": datetime(2026, 7, 1, tzinfo=timezone.utc)},
    )
    assert str(res_apr.scalar_one()) == apr_id
    assert str(res_jul.scalar_one()) == jun_id


# ---------------------------------------------------------------------------
# AC-5 — AED→AED forzado a rate=1
# ---------------------------------------------------------------------------
async def test_aed_aed_identity_forces_rate_one(db_session: "AsyncSession") -> None:
    # Limpiamos la identity row del seed mig 017 (la migración la inserta con
    # 2026-04-01, pero queremos un test puro).
    await db_session.execute(
        text("DELETE FROM fx_rates WHERE from_currency='AED' AND to_currency='AED'")
    )
    new_id = await _insert_rate(
        db_session,
        from_c="AED",
        to_c="AED",
        rate=999.5,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
        source="manual",
    )
    row = await _row_by_id(db_session, new_id)
    assert Decimal(str(row["rate"])) == Decimal("1.00000000")


# ---------------------------------------------------------------------------
# AC-6 — rate=0 → bloqueo del trigger
# ---------------------------------------------------------------------------
async def test_zero_rate_blocked_by_trigger_or_constraint(
    db_session: "AsyncSession",
) -> None:
    await _purge_pair(db_session, "EUR", "AED")
    with pytest.raises((IntegrityError, InternalError, Exception)) as ei:
        await _insert_rate(
            db_session,
            from_c="EUR",
            to_c="AED",
            rate=0,
            effective_from=datetime(2026, 6, 1, tzinfo=timezone.utc),
        )
    msg = str(ei.value)
    # Cualquiera de los dos: trigger o CHECK constraint.
    assert (
        "fx_rate_must_be_positive" in msg
        or "ck_fx_rate_positive" in msg
        or "check constraint" in msg
    )


# ---------------------------------------------------------------------------
# AC-7 — allow_retroactive=true permite el insert
# ---------------------------------------------------------------------------
async def test_allow_retroactive_flag_permits_insert(
    db_session: "AsyncSession",
) -> None:
    await _purge_pair(db_session, "EUR", "AED")
    await _insert_rate(
        db_session,
        from_c="EUR",
        to_c="AED",
        rate=4.29,
        effective_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    # Flag scoped al statement: SET LOCAL en la misma transacción.
    await db_session.execute(text("SET LOCAL fx.allow_retroactive = 'true'"))
    new_id = await _insert_rate(
        db_session,
        from_c="EUR",
        to_c="AED",
        rate=4.10,
        effective_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    new = await _row_by_id(db_session, new_id)
    assert new["effective_to"] is None  # NEW se inserta como vigente.


# ---------------------------------------------------------------------------
# AC-8 — pares independientes
# ---------------------------------------------------------------------------
async def test_pairs_are_independent(db_session: "AsyncSession") -> None:
    await _purge_pair(db_session, "EUR", "AED")
    await _purge_pair(db_session, "USD", "AED")
    eur_id = await _insert_rate(
        db_session,
        from_c="EUR",
        to_c="AED",
        rate=4.29,
        effective_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    usd_id = await _insert_rate(
        db_session,
        from_c="USD",
        to_c="AED",
        rate=3.67,
        effective_from=datetime(2026, 4, 1, tzinfo=timezone.utc),
    )
    # Cerramos EUR→AED con un rate nuevo.
    await _insert_rate(
        db_session,
        from_c="EUR",
        to_c="AED",
        rate=4.18,
        effective_from=datetime(2026, 6, 12, tzinfo=timezone.utc),
    )
    eur = await _row_by_id(db_session, eur_id)
    usd = await _row_by_id(db_session, usd_id)
    assert eur["effective_to"] is not None
    assert usd["effective_to"] is None  # USD→AED intacto.
