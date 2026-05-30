"""Integration tests — CostService vigencia por rangos (T3+T4+T5).

Cubren el comportamiento de servicio sobre la migración ``20260603_148``:

- ``create_cost`` con ``valid_from`` real auto-encadena: cierra la fila abierta
  previa (``valid_to = vf - 1 día``) antes de insertar la nueva (``valid_to``
  NULL). La exclusión GiST ``ex_costs_no_overlap`` valida no-solape en el flush.
- ``cost_as_of`` resuelve la fila vigente a una fecha dada.
- ``close_cost`` fija ``valid_to`` (descatalogar / cierre sin sucesor).
- ``update_cost`` corrige IN-PLACE la misma fila (re-estampa FX/landed).

Nota: FBA exige el breakdown completo ``{fob, freight, customs, fba_fees,
payment_fees}`` (seed mig 004). Usamos ``currency_origin='AED'`` para evitar
dependencia de un FX rate vigente (AED→AED no convierte).
"""

from __future__ import annotations

import datetime as dt

import pytest

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]

# Breakdown completo para FBA: el seed (mig 004) exige las claves required
# ``fob, freight, customs, fba_fees, payment_fees`` (sin sufijo). Para que el
# trigger las trate como AED (sin FX) usamos además las claves ``*_aed``.
# ``currency_origin='AED'`` ⇒ AED→AED no convierte.
_FBA_BASE = {
    "fob": 100,
    "freight": 10,
    "customs": 5,
    "fba_fees": 8,
    "payment_fees": 3,
}


def _bk(*, fob_aed: int | None = None) -> dict:
    out = dict(_FBA_BASE)
    if fob_aed is not None:
        out["fob"] = fob_aed
    return out


async def test_create_chains_previous(db_session, make_product):
    from app.services.costs.cost_service import CostService

    await make_product("_CHAIN")
    svc = CostService(db_session)
    res_a = await svc.create_cost(
        sku="_CHAIN",
        scheme_code="FBA",
        supplier_code=None,
        currency_origin="AED",
        breakdown=_bk(fob_aed=100),
        valid_from=dt.date(2026, 1, 1),
    )
    a = res_a.cost
    res_b = await svc.create_cost(
        sku="_CHAIN",
        scheme_code="FBA",
        supplier_code=None,
        currency_origin="AED",
        breakdown=_bk(fob_aed=120),
        valid_from=dt.date(2026, 6, 1),
    )
    b = res_b.cost
    await db_session.refresh(a)
    assert a.valid_to == dt.date(2026, 5, 31)
    assert b.valid_to is None


async def test_as_of_returns_right_range(db_session, make_product):
    from app.services.costs.cost_service import CostService

    await make_product("_ASOF")
    svc = CostService(db_session)
    await svc.create_cost(
        sku="_ASOF",
        scheme_code="FBA",
        supplier_code=None,
        currency_origin="AED",
        breakdown=_bk(fob_aed=100),
        valid_from=dt.date(2026, 1, 1),
    )
    await svc.create_cost(
        sku="_ASOF",
        scheme_code="FBA",
        supplier_code=None,
        currency_origin="AED",
        breakdown=_bk(fob_aed=120),
        valid_from=dt.date(2026, 6, 1),
    )
    r1 = await svc.cost_as_of(
        sku="_ASOF", scheme_code="FBA", supplier_code=None, on=dt.date(2026, 3, 1)
    )
    r2 = await svc.cost_as_of(
        sku="_ASOF", scheme_code="FBA", supplier_code=None, on=dt.date(2026, 7, 1)
    )
    assert r1 is not None and r1.valid_from == dt.date(2026, 1, 1)
    assert r2 is not None and r2.valid_from == dt.date(2026, 6, 1)


async def test_as_of_returns_none_before_first_range(db_session, make_product):
    from app.services.costs.cost_service import CostService

    await make_product("_ASOF_NONE")
    svc = CostService(db_session)
    await svc.create_cost(
        sku="_ASOF_NONE",
        scheme_code="FBA",
        supplier_code=None,
        currency_origin="AED",
        breakdown=_bk(),
        valid_from=dt.date(2026, 6, 1),
    )
    r = await svc.cost_as_of(
        sku="_ASOF_NONE", scheme_code="FBA", supplier_code=None, on=dt.date(2026, 1, 1)
    )
    assert r is None


async def test_close_sets_valid_to(db_session, make_product):
    from app.services.costs.cost_service import CostService

    await make_product("_CLOSE")
    svc = CostService(db_session)
    res = await svc.create_cost(
        sku="_CLOSE",
        scheme_code="FBA",
        supplier_code=None,
        currency_origin="AED",
        breakdown=_bk(fob_aed=100),
        valid_from=dt.date(2026, 1, 1),
    )
    c = res.cost
    await svc.close_cost(cost_id=c.id, valid_to=dt.date(2026, 12, 31))
    await db_session.refresh(c)
    assert c.valid_to == dt.date(2026, 12, 31)


async def test_update_corrects_in_place(db_session, make_product):
    """``update_cost`` corrige la MISMA fila (mismo id) y re-estampa landed."""
    from app.services.costs.cost_service import CostService

    await make_product("_UPD")
    svc = CostService(db_session)
    res = await svc.create_cost(
        sku="_UPD",
        scheme_code="FBA",
        supplier_code=None,
        currency_origin="AED",
        breakdown=_bk(fob_aed=100),
        valid_from=dt.date(2026, 1, 1),
    )
    c = res.cost
    original_id = c.id
    landed_before = c.scheme_landed_aed

    upd = await svc.update_cost(
        original_id,
        actor_id=None,
        breakdown=_bk(fob_aed=200),
    )
    assert upd.cost.id == original_id  # in-place: mismo id, no nueva versión
    await db_session.refresh(c)
    assert c.breakdown["fob"] == 200
    # landed re-estampado por el trigger AFTER UPDATE (200 > 100 base).
    assert c.scheme_landed_aed != landed_before
