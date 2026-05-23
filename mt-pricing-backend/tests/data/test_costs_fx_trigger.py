"""Integration tests del trigger ``costs_stamp_fx_trg`` y
``costs_compute_landed_aed_trg`` (US-1A-04-02 — migración 018).

Estrategia: Postgres efímero vía testcontainers + ``alembic upgrade head``.
Cada test usa ``db_session`` con rollback al final.

Cobertura BDD (≥6 casos cubriendo todos los AC del trigger):
1. INSERT con currency_origin='EUR', sin fx_rate_id explícito → trigger estampa
   fx_rate_id correctamente (AC#1).
2. INSERT con fx_rate_id explícito → trigger respeta y NO sobrescribe (AC#2).
3. INSERT con currency_origin='EUR' y NO existe rate vigente → falla con
   ``fx_rate_not_found_at_effective_at`` (AC#3).
4. INSERT con currency_origin='AED' → fx_rate_id permanece NULL, no error (AC#1).
5. INSERT con breakdown ``{fob_eur, freight_eur}`` → ``scheme_landed_aed`` se
   calcula automáticamente (AC#4).
6. UPDATE de ``breakdown`` → ``scheme_landed_aed`` se recalcula (AC#6 indirecto).
7. UNIQUE parcial (status='active') previene 2 rows active para el mismo
   (sku, scheme_code, supplier_code).
8. INSERT con ``fx_inferred=true`` queda marcado para audit (AC#5).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
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
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Fixtures de soporte — productos, suppliers, schemes, fx_rates ya seeded por
# las migraciones (010 + 017). Sólo necesitamos un SKU dummy para FK.
# ---------------------------------------------------------------------------
async def _ensure_test_sku(session: AsyncSession, sku: str = "TEST-COST-001") -> str:
    """Inserta un product mínimo si no existe y retorna su sku."""
    await session.execute(
        text(
            """
            INSERT INTO products (sku, family, brand, data_quality)
            VALUES (:sku, 'ball_valve', 'TestBrand', 'complete')
            ON CONFLICT (sku) DO NOTHING
            """
        ),
        {"sku": sku},
    )
    return sku


async def _ensure_test_supplier(
    session: AsyncSession, code: str = "TEST_SUP_FX"
) -> str:
    await session.execute(
        text(
            """
            INSERT INTO suppliers (code, name, currency, active)
            VALUES (:code, 'Test Supplier FX', 'EUR', true)
            ON CONFLICT (code) DO NOTHING
            """
        ),
        {"code": code},
    )
    return code


async def _purge_costs(session: AsyncSession, sku: str) -> None:
    await session.execute(text("DELETE FROM costs WHERE sku = :sku"), {"sku": sku})


async def _insert_cost(
    session: AsyncSession,
    *,
    sku: str,
    scheme_code: str,
    currency_origin: str,
    effective_at: datetime,
    breakdown: dict,
    supplier_code: str | None = None,
    fx_rate_id: str | None = None,
    fx_inferred: bool = False,
    status: str = "active",
    version: int = 1,
) -> str:
    """INSERT plain text — testea trigger directo, no ORM."""
    import json

    bk = json.dumps(breakdown).replace("'", "''")
    fx_sql = f"'{fx_rate_id}'::uuid" if fx_rate_id else "NULL"
    sup_sql = f"'{supplier_code}'" if supplier_code else "NULL"
    sql = text(
        f"""
        INSERT INTO costs (
            sku, scheme_code, supplier_code, currency_origin,
            fx_rate_id, breakdown, effective_at, status, fx_inferred, version
        ) VALUES (
            :sku, :scheme, {sup_sql}, :cur,
            {fx_sql}, '{bk}'::jsonb, :eff, :st, :fxi, :ver
        )
        RETURNING id
        """
    )
    res = await session.execute(
        sql,
        {
            "sku": sku,
            "scheme": scheme_code,
            "cur": currency_origin,
            "eff": effective_at,
            "st": status,
            "fxi": fx_inferred,
            "ver": version,
        },
    )
    return str(res.scalar_one())


async def _row_by_id(session: AsyncSession, row_id: str) -> dict:
    res = await session.execute(
        text(
            """
            SELECT id, sku, scheme_code, supplier_code, currency_origin,
                   fx_rate_id, breakdown, scheme_landed_aed, effective_at,
                   status, fx_inferred, version
              FROM costs WHERE id = :id
            """
        ),
        {"id": row_id},
    )
    row = res.first()
    assert row is not None, f"Cost {row_id} not found"
    return dict(row._mapping)  # type: ignore[attr-defined]


async def _ensure_eur_aed_rate(
    session: AsyncSession, *, rate: float = 4.29, effective_from: datetime | None = None
) -> str:
    """Asegura un rate EUR→AED vigente. Retorna su id."""
    eff = effective_from or datetime(2026, 1, 1, tzinfo=UTC)
    # Check if there's already an active rate covering effective_from.
    res = await session.execute(
        text(
            """
            SELECT id FROM fx_rates
            WHERE from_currency='EUR' AND to_currency='AED'
              AND effective_from <= :eff
              AND (effective_to IS NULL OR effective_to > :eff)
            ORDER BY effective_from DESC LIMIT 1
            """
        ),
        {"eff": eff},
    )
    existing = res.scalar_one_or_none()
    if existing:
        return str(existing)
    # Insert a brand-new historical rate (mig 017 trigger may auto-close, OK).
    res = await session.execute(
        text(
            """
            INSERT INTO fx_rates (from_currency, to_currency, rate, effective_from, source)
            VALUES ('EUR', 'AED', :r, :eff, 'manual')
            RETURNING id
            """
        ),
        {"r": str(Decimal(str(rate))), "eff": eff},
    )
    return str(res.scalar_one())


# ---------------------------------------------------------------------------
# AC-1 — trigger estampa fx_rate_id automáticamente (currency_origin='EUR')
# ---------------------------------------------------------------------------
async def test_trigger_stamps_fx_rate_id_when_currency_eur(
    db_session: AsyncSession,
) -> None:
    sku = await _ensure_test_sku(db_session)
    await _purge_costs(db_session, sku)
    await _ensure_eur_aed_rate(db_session, rate=4.29)
    eff = datetime(2026, 6, 12, tzinfo=UTC)

    cost_id = await _insert_cost(
        db_session,
        sku=sku,
        scheme_code="FBA",
        currency_origin="EUR",
        effective_at=eff,
        breakdown={"fob_eur": "12.40", "freight_eur": "1.80"},
    )
    row = await _row_by_id(db_session, cost_id)
    assert row["fx_rate_id"] is not None, "trigger debió estampar fx_rate_id"
    assert row["currency_origin"] == "EUR"


# ---------------------------------------------------------------------------
# AC-2 — fx_rate_id explícito se respeta y NO se sobrescribe
# ---------------------------------------------------------------------------
async def test_explicit_fx_rate_id_is_preserved(
    db_session: AsyncSession,
) -> None:
    sku = await _ensure_test_sku(db_session)
    await _purge_costs(db_session, sku)
    fx_a = await _ensure_eur_aed_rate(db_session, rate=4.29)
    eff = datetime(2026, 6, 12, tzinfo=UTC)

    cost_id = await _insert_cost(
        db_session,
        sku=sku,
        scheme_code="FBA",
        currency_origin="EUR",
        effective_at=eff,
        breakdown={"fob_eur": "10"},
        fx_rate_id=fx_a,  # explicit
    )
    row = await _row_by_id(db_session, cost_id)
    assert str(row["fx_rate_id"]) == fx_a


# ---------------------------------------------------------------------------
# AC-3 — sin rate vigente para currency_origin → trigger falla
# ---------------------------------------------------------------------------
async def test_missing_fx_rate_raises_with_canonical_code(
    db_session: AsyncSession,
) -> None:
    sku = await _ensure_test_sku(db_session)
    await _purge_costs(db_session, sku)
    # Use a currency that almost certainly has no rate seeded.
    # Make sure GBP currency exists in `currencies`.
    await db_session.execute(
        text(
            """
            INSERT INTO currencies (code, name, active)
            VALUES ('GBP', 'Pound Sterling', true)
            ON CONFLICT (code) DO NOTHING
            """
        )
    )
    # Wipe any GBP→AED rates the seed/CI may have created.
    await db_session.execute(
        text("DELETE FROM fx_rates WHERE from_currency='GBP' AND to_currency='AED'")
    )

    eff = datetime(2026, 6, 12, tzinfo=UTC)
    with pytest.raises((IntegrityError, InternalError, Exception)) as ei:
        await _insert_cost(
            db_session,
            sku=sku,
            scheme_code="FBA",
            currency_origin="GBP",
            effective_at=eff,
            breakdown={"fob_gbp": "10"},
        )
    assert "fx_rate_not_found_at_effective_at" in str(ei.value)


# ---------------------------------------------------------------------------
# AC-1 (bis) — currency='AED' → fx_rate_id permanece NULL, no falla
# ---------------------------------------------------------------------------
async def test_aed_origin_keeps_fx_rate_id_null(
    db_session: AsyncSession,
) -> None:
    sku = await _ensure_test_sku(db_session)
    await _purge_costs(db_session, sku)
    eff = datetime(2026, 6, 12, tzinfo=UTC)

    cost_id = await _insert_cost(
        db_session,
        sku=sku,
        scheme_code="FBA",
        currency_origin="AED",
        effective_at=eff,
        breakdown={"fob_aed": "47.90", "customs_aed": "2.10"},
    )
    row = await _row_by_id(db_session, cost_id)
    assert row["fx_rate_id"] is None, "AED→AED no debe estampar fx_rate_id"


# ---------------------------------------------------------------------------
# AC-4 — scheme_landed_aed se calcula automáticamente desde el breakdown
# ---------------------------------------------------------------------------
async def test_scheme_landed_aed_computed_on_insert(
    db_session: AsyncSession,
) -> None:
    sku = await _ensure_test_sku(db_session)
    await _purge_costs(db_session, sku)
    await _ensure_eur_aed_rate(db_session, rate=4.29)
    eff = datetime(2026, 6, 12, tzinfo=UTC)

    cost_id = await _insert_cost(
        db_session,
        sku=sku,
        scheme_code="FBA",
        currency_origin="EUR",
        effective_at=eff,
        # 12.40 + 1.80 = 14.20 EUR → 14.20 * 4.29 = 60.918 AED.
        # + customs_aed=2.10 = 63.018 AED
        breakdown={
            "fob_eur": "12.40",
            "freight_eur": "1.80",
            "customs_aed": "2.10",
        },
    )
    row = await _row_by_id(db_session, cost_id)
    assert row["scheme_landed_aed"] is not None
    landed = Decimal(str(row["scheme_landed_aed"]))
    expected = (Decimal("12.40") + Decimal("1.80")) * Decimal("4.29") + Decimal("2.10")
    assert landed == expected.quantize(Decimal("0.0001"))


# ---------------------------------------------------------------------------
# AC-6 — UPDATE de breakdown recalcula scheme_landed_aed
# ---------------------------------------------------------------------------
async def test_update_breakdown_recomputes_landed_aed(
    db_session: AsyncSession,
) -> None:
    sku = await _ensure_test_sku(db_session)
    await _purge_costs(db_session, sku)
    await _ensure_eur_aed_rate(db_session, rate=4.29)
    eff = datetime(2026, 6, 12, tzinfo=UTC)

    cost_id = await _insert_cost(
        db_session,
        sku=sku,
        scheme_code="FBA",
        currency_origin="EUR",
        effective_at=eff,
        breakdown={"fob_eur": "10"},
    )
    row1 = await _row_by_id(db_session, cost_id)
    initial = Decimal(str(row1["scheme_landed_aed"]))
    assert initial == (Decimal("10") * Decimal("4.29")).quantize(Decimal("0.0001"))

    # UPDATE breakdown → trigger AFTER recalcula.
    await db_session.execute(
        text(
            """
            UPDATE costs SET breakdown = '{"fob_eur": "20"}'::jsonb
             WHERE id = :id
            """
        ),
        {"id": cost_id},
    )
    row2 = await _row_by_id(db_session, cost_id)
    updated = Decimal(str(row2["scheme_landed_aed"]))
    assert updated == (Decimal("20") * Decimal("4.29")).quantize(Decimal("0.0001"))


# ---------------------------------------------------------------------------
# UNIQUE parcial — sólo 1 active por (sku, scheme_code, supplier_code).
# ---------------------------------------------------------------------------
async def test_unique_active_constraint_prevents_duplicate_active(
    db_session: AsyncSession,
) -> None:
    sku = await _ensure_test_sku(db_session)
    await _purge_costs(db_session, sku)
    await _ensure_eur_aed_rate(db_session, rate=4.29)
    eff = datetime(2026, 6, 12, tzinfo=UTC)

    await _insert_cost(
        db_session,
        sku=sku,
        scheme_code="FBA",
        currency_origin="EUR",
        effective_at=eff,
        breakdown={"fob_eur": "10"},
        status="active",
        version=1,
    )
    with pytest.raises((IntegrityError, InternalError, Exception)) as ei:
        await _insert_cost(
            db_session,
            sku=sku,
            scheme_code="FBA",
            currency_origin="EUR",
            effective_at=eff,
            breakdown={"fob_eur": "11"},
            status="active",
            version=2,
        )
    msg = str(ei.value).lower()
    assert "uq_costs_active_combo" in msg or "duplicate" in msg or "unique" in msg


# ---------------------------------------------------------------------------
# AC-5 — fx_inferred=true persiste correctamente para audit
# ---------------------------------------------------------------------------
async def test_fx_inferred_flag_is_persisted(db_session: AsyncSession) -> None:
    sku = await _ensure_test_sku(db_session)
    await _purge_costs(db_session, sku)
    await _ensure_eur_aed_rate(db_session, rate=4.29)
    eff = datetime(2026, 6, 12, tzinfo=UTC)

    cost_id = await _insert_cost(
        db_session,
        sku=sku,
        scheme_code="FBA",
        currency_origin="EUR",
        effective_at=eff,
        breakdown={"fob_eur": "10"},
        fx_inferred=True,
    )
    row = await _row_by_id(db_session, cost_id)
    assert row["fx_inferred"] is True
