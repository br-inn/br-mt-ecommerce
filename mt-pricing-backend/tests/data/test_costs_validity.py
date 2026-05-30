"""Tests de migración — costs: vigencia por rangos (valid_from/valid_to).

Cubren la migración ``20260603_148_costs_validity_ranges``:

- ``test_exclusion_rejects_overlapping_ranges``: la exclusión GiST
  ``ex_costs_no_overlap`` rechaza dos rangos solapados para la misma clave
  ``(sku, scheme_code, coalesce(supplier_code, ''))``.
- ``test_columns_exist_and_status_dropped``: ``valid_from``/``valid_to`` existen
  y ``status``/``effective_at`` fueron dropeadas.
- ``test_open_ended_range_accepted``: una fila con ``valid_to = NULL`` (rango
  abierto) es aceptada y consultable — documenta que ``daterange(vf, NULL, '[]')``
  no genera error (upper bound infinito).

IMPORTANTE: usar SQL crudo (``text(...)``) + ``information_schema`` — NO el ORM
``Cost`` model, que en este punto aún referencia ``effective_at``/``status``
(se actualiza en Task 2). Acoplar al modelo rompería estos tests.
"""

from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


# Raw INSERT con TODAS las columnas NOT NULL de costs tras la migración:
#   id (default gen_random_uuid), sku (FK products.sku, NOT NULL),
#   scheme_code (FK schemes.code, NOT NULL), currency_origin (NOT NULL,
#   default 'AED'), breakdown (NOT NULL, default '{}'), version (NOT NULL,
#   default 1), valid_from (NOT NULL), valid_to (NULL ok).
_INSERT = text(
    """
    INSERT INTO costs (id, sku, scheme_code, currency_origin, breakdown,
                       valid_from, valid_to, version)
    VALUES (gen_random_uuid(), :sku, 'FBA', 'AED', '{}'::jsonb,
            :vf, :vt, :ver)
    """
)


async def test_exclusion_rejects_overlapping_ranges(db_session, make_product):
    """Dos costes solapados para la misma clave → ExclusionViolation."""
    from sqlalchemy.exc import IntegrityError

    await make_product("_TEST_OVL")

    # Rango 1: [2026-01-01, 2026-06-30]
    await db_session.execute(
        _INSERT,
        {
            "sku": "_TEST_OVL",
            "vf": dt.date(2026, 1, 1),
            "vt": dt.date(2026, 6, 30),
            "ver": 1,
        },
    )

    # Rango 2: [2026-06-01, ∞) — solapa con el rango 1 en junio → debe fallar.
    with pytest.raises(IntegrityError):
        await db_session.execute(
            _INSERT,
            {
                "sku": "_TEST_OVL",
                "vf": dt.date(2026, 6, 1),
                "vt": None,
                "ver": 2,
            },
        )


async def test_open_ended_range_accepted(db_session, make_product):
    """Una fila con valid_to = NULL (rango abierto) se acepta y es consultable.

    Documenta que la exclusión con ``daterange(valid_from, valid_to, '[]')`` y
    ``valid_to = NULL`` produce un rango con cota superior infinita (no error).
    """
    await make_product("_TEST_OPEN")

    await db_session.execute(
        _INSERT,
        {
            "sku": "_TEST_OPEN",
            "vf": dt.date(2026, 1, 1),
            "vt": None,
            "ver": 1,
        },
    )

    row = (
        await db_session.execute(
            text("SELECT valid_from, valid_to FROM costs WHERE sku = :sku AND scheme_code = 'FBA'"),
            {"sku": "_TEST_OPEN"},
        )
    ).one()

    assert row.valid_from == dt.date(2026, 1, 1)
    assert row.valid_to is None


async def test_columns_exist_and_status_dropped(db_session):
    """valid_from/valid_to presentes; status/effective_at ausentes."""
    cols = (
        (
            await db_session.execute(
                text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'costs'"
                )
            )
        )
        .scalars()
        .all()
    )

    assert "valid_from" in cols
    assert "valid_to" in cols
    assert "status" not in cols
    assert "effective_at" not in cols


async def test_model_hybrids(db_session, make_product):
    """El modelo ORM expone valid_from/valid_to reales y hybrids de compat.

    - ``effective_at`` (hybrid) devuelve ``valid_from``.
    - ``status`` (hybrid) se deriva por fecha: 'active' (rango abierto) o
      'superseded'.
    - ``valid_to`` real es NULL para un rango abierto.
    """
    from app.db.models.cost import Cost

    await make_product("_HYB")

    c = Cost(
        sku="_HYB",
        scheme_code="FBA",
        currency_origin="AED",
        breakdown={},
        valid_from=dt.date(2026, 1, 1),
    )
    db_session.add(c)
    await db_session.flush()
    await db_session.refresh(c)

    assert c.effective_at == dt.date(2026, 1, 1)
    assert c.status in ("active", "superseded")
    assert c.valid_to is None
