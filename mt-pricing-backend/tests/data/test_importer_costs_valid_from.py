"""Integration test del flujo importer de costos con vigencia por rangos.

Ejercita differ + applier contra el ``CostService`` real sobre una DB
efímera (testcontainers + alembic head). Cubre Task 8:

- Un import con ``valid_from`` futuro crea un rango NUEVO aunque exista un
  coste abierto vigente hoy, y el auto-encadenado del service cierra el rango
  previo en ``valid_from - 1``.
- El differ resuelve CREATE vs NO_CHANGE comparando contra el coste vigente AL
  ``valid_from`` de la fila (no sólo "el coste activo").

Estrategia idéntica a ``tests/data/test_costs_fx_trigger.py``: ``db_session``
(rollback al final) + product seed mínimo. La FBA scheme y la currency AED ya
vienen seeded por las migraciones, así que usamos AED para evitar depender de
fx_rates.
"""

from __future__ import annotations

import os
from datetime import date
from typing import TYPE_CHECKING
from uuid import UUID

import pytest
from sqlalchemy import text

from app.services.costs.cost_service import CostService
from app.services.importer_costs.applier import apply_cost_diffs
from app.services.importer_costs.differ import CostRowAction, compute_cost_diff
from app.services.importer_costs.parser import CostRow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]

# La FBA scheme (seeded por migraciones) exige estos campos en el breakdown.
_FBA_REQUIRED = ("fob", "freight", "customs", "fba_fees", "payment_fees")


def _fba_breakdown(fob: str) -> dict[str, str]:
    """Breakdown válido para FBA (cumple required) parametrizando `fob`."""
    bd = {k: "1" for k in _FBA_REQUIRED}
    bd["fob"] = fob
    return bd


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def _ensure_test_user(session: AsyncSession, email: str) -> UUID:
    """Inserta (idempotente) un user mínimo y devuelve su id (FK costs.created_by)."""
    res = await session.execute(
        text(
            """
            INSERT INTO users (id, email, is_active)
            VALUES (gen_random_uuid(), :email, true)
            ON CONFLICT (email) DO UPDATE SET is_active = true
            RETURNING id
            """
        ),
        {"email": email},
    )
    return res.scalar_one()


async def _ensure_test_sku(session: AsyncSession, sku: str) -> str:
    await session.execute(
        text(
            """
            INSERT INTO products (sku, family, brand, data_quality, brand_id, family_id)
            SELECT :sku, 'ball_valve', 'TestBrand', 'complete',
                   (SELECT id FROM brands WHERE code = 'default'),
                   (SELECT id FROM families WHERE code = 'default')
            ON CONFLICT (sku) DO NOTHING
            """
        ),
        {"sku": sku},
    )
    return sku


class _Actor:
    def __init__(self, user_id: UUID, email: str = "importer@mt.ae") -> None:
        self.id = user_id
        self.email = email


def _row(*, sku: str, valid_from: date, breakdown: dict, supplier: str | None = None) -> CostRow:
    return CostRow(
        row_index=1,
        sku=sku,
        scheme_code="FBA",
        supplier_code=supplier,
        currency="AED",
        total=None,
        breakdown=dict(breakdown),
        valid_from=valid_from,
        errors=[],
    )


async def _ranges(session: AsyncSession, sku: str) -> list[dict]:
    res = await session.execute(
        text(
            """
            SELECT valid_from, valid_to, breakdown
              FROM costs
             WHERE sku = :sku AND scheme_code = 'FBA'
             ORDER BY valid_from
            """
        ),
        {"sku": sku},
    )
    return [dict(r._mapping) for r in res.all()]


async def test_future_dated_import_chains_previous_open_cost(db_session: AsyncSession) -> None:
    """Existe un coste abierto desde hoy; un import futuro crea un rango nuevo y
    encadena (cierra) el previo en ``valid_from - 1``."""
    sku = await _ensure_test_sku(db_session, "TEST-IMP-FUT")
    await db_session.execute(text("DELETE FROM costs WHERE sku = :sku"), {"sku": sku})
    user_id = await _ensure_test_user(db_session, "importer-fut@mt.ae")

    svc = CostService(db_session)
    actor = _Actor(user_id)

    # Coste vigente actual (rango abierto) desde 2026-01-01.
    current_from = date(2026, 1, 1)
    current_bd = _fba_breakdown("10")
    await svc.create_cost(
        sku=sku,
        scheme_code="FBA",
        currency_origin="AED",
        valid_from=current_from,
        breakdown=current_bd,
        actor_id=actor.id,
    )
    await db_session.flush()

    # Import con una fila FUTURA con breakdown distinto. El coste abierto cubre
    # la fecha futura (valid_to=NULL), así que el differ la marca UPDATE — pero
    # el applier llama create_cost, que auto-encadena: cierra el rango previo en
    # future_from - 1 e inserta un rango nuevo abierto. El efecto persistido es
    # el mismo que un CREATE: dos rangos consecutivos sin solape.
    future_from = date(2027, 6, 1)
    future_bd = _fba_breakdown("25")
    rows = [_row(sku=sku, valid_from=future_from, breakdown=future_bd)]
    diffs, orphans = await compute_cost_diff(db_session, rows)
    assert orphans.sku_not_in_pim == []
    assert diffs[0].action in (CostRowAction.CREATE, CostRowAction.UPDATE)

    res = await apply_cost_diffs(diffs, actor, cost_service=svc, run_id="run-fut")
    assert res.created + res.updated == 1, res.failure_details
    assert res.errors == 0 and res.errors_fx_missing == 0
    await db_session.flush()

    ranges = await _ranges(db_session, sku)
    assert len(ranges) == 2
    prev, new = ranges
    # El rango previo quedó cerrado en future_from - 1 (auto-encadenado).
    assert prev["valid_from"] == current_from
    assert prev["valid_to"] == date(2027, 5, 31)
    assert prev["breakdown"] == current_bd
    # El rango nuevo es abierto desde la fecha futura.
    assert new["valid_from"] == future_from
    assert new["valid_to"] is None
    assert new["breakdown"] == future_bd


async def test_future_dated_import_creates_when_prior_range_closed(
    db_session: AsyncSession,
) -> None:
    """Si el coste previo está CERRADO antes de la fecha futura, el differ marca
    CREATE (no hay coste vigente a esa fecha) y se inserta un rango nuevo."""
    sku = await _ensure_test_sku(db_session, "TEST-IMP-CRT")
    await db_session.execute(text("DELETE FROM costs WHERE sku = :sku"), {"sku": sku})
    user_id = await _ensure_test_user(db_session, "importer-crt@mt.ae")

    svc = CostService(db_session)
    actor = _Actor(user_id)

    # Coste cerrado [2026-01-01, 2026-12-31].
    first = await svc.create_cost(
        sku=sku,
        scheme_code="FBA",
        currency_origin="AED",
        valid_from=date(2026, 1, 1),
        breakdown=_fba_breakdown("10"),
        actor_id=actor.id,
    )
    await svc.close_cost(cost_id=first.cost.id, valid_to=date(2026, 12, 31), actor_id=actor.id)
    await db_session.flush()

    # Fila futura sin coste vigente a esa fecha → CREATE.
    future_from = date(2027, 6, 1)
    future_bd = _fba_breakdown("30")
    rows = [_row(sku=sku, valid_from=future_from, breakdown=future_bd)]
    diffs, _ = await compute_cost_diff(db_session, rows)
    assert diffs[0].action == CostRowAction.CREATE

    res = await apply_cost_diffs(diffs, actor, cost_service=svc, run_id="run-crt")
    assert res.created == 1, res.failure_details
    await db_session.flush()

    ranges = await _ranges(db_session, sku)
    assert len(ranges) == 2
    # El rango previo conserva su valid_to (no se re-cierra: ya estaba cerrado
    # antes del nuevo valid_from).
    assert ranges[0]["valid_to"] == date(2026, 12, 31)
    assert ranges[1]["valid_from"] == future_from
    assert ranges[1]["valid_to"] is None


async def test_import_row_no_change_when_identical_at_its_valid_from(
    db_session: AsyncSession,
) -> None:
    """Una fila cuyo coste vigente a su valid_from es idéntico → NO_CHANGE
    (no se aplica nada)."""
    sku = await _ensure_test_sku(db_session, "TEST-IMP-NOCHG")
    await db_session.execute(text("DELETE FROM costs WHERE sku = :sku"), {"sku": sku})
    user_id = await _ensure_test_user(db_session, "importer-nochg@mt.ae")

    svc = CostService(db_session)
    actor = _Actor(user_id)
    bd = _fba_breakdown("10")
    await svc.create_cost(
        sku=sku,
        scheme_code="FBA",
        currency_origin="AED",
        valid_from=date(2026, 1, 1),
        breakdown=bd,
        actor_id=actor.id,
    )
    await db_session.flush()

    # Fila vigente más adelante pero con breakdown idéntico → NO_CHANGE.
    rows = [_row(sku=sku, valid_from=date(2026, 9, 1), breakdown=dict(bd))]
    diffs, _ = await compute_cost_diff(db_session, rows)
    assert diffs[0].action == CostRowAction.NO_CHANGE

    res = await apply_cost_diffs(diffs, actor, cost_service=svc, run_id="run-noc")
    assert res.no_change == 1
    assert res.created == 0
    await db_session.flush()

    # Sigue habiendo un único rango.
    assert len(await _ranges(db_session, sku)) == 1
