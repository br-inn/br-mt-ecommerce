"""Stage 3 (Wave 11) — ProductRepository.list_paginated_with_filters filtros.

Verifica que los nuevos kwargs ``division_code``, ``series_id``, ``material_id``
y ``tier_code`` se traducen a las cláusulas SQL esperadas (EXISTS para M:N
divisions, equality para series_id/material_id, EXISTS+JOIN para tier_code) y
que la query no rompe cuando se mezclan con los filtros pre-existentes.

Patrón: mock de ``AsyncSession`` que captura el ``stmt`` enviado a
``execute`` y se inspecciona el SQL compilado contra Postgres dialect.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.dialects import postgresql

from app.repositories.product import ProductRepository

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _fake_session() -> tuple[Any, list[Any]]:
    """Devuelve (session_mock, captured_stmts).

    Cada llamada a ``execute`` añade el stmt a ``captured_stmts`` y devuelve
    un Result vacío. Soporta tanto la query principal (`scalars().all()`) como
    el opcional ``count(*)`` (`scalar_one()`).
    """
    captured: list[Any] = []

    async def _execute(stmt: Any) -> Any:  # noqa: ANN401
        captured.append(stmt)
        result = MagicMock()
        # scalars().all() para la lista; scalar_one() para count.
        result.scalars.return_value.all.return_value = []
        result.scalar_one.return_value = 0
        return result

    session = MagicMock()
    session.execute = AsyncMock(side_effect=_execute)
    # bind.dialect.name → postgresql para forzar la rama tsvector y compilar SQL.
    session.bind = MagicMock()
    session.bind.dialect = MagicMock()
    session.bind.dialect.name = "postgresql"
    return session, captured


def _compile_sql(stmt: Any) -> str:
    """Compila el statement a string SQL Postgres (literal_binds=False)."""
    return str(
        stmt.compile(
            dialect=postgresql.dialect(),
            compile_kwargs={"literal_binds": False},
        )
    ).lower()


# ---------------------------------------------------------------------------
# division_code → EXISTS sobre product_divisions JOIN divisions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage3_division_code_filter_emits_exists_clause() -> None:
    session, captured = _fake_session()
    repo = ProductRepository(session)
    await repo.list_paginated_with_filters(division_code="hidrosanitario")

    assert len(captured) == 1
    sql = _compile_sql(captured[0])
    assert "exists" in sql
    assert "product_divisions" in sql
    assert "divisions" in sql
    # El JOIN va contra divisions.code.
    assert "divisions.code" in sql


@pytest.mark.asyncio
async def test_stage3_series_id_filter_emits_equality_clause() -> None:
    session, captured = _fake_session()
    repo = ProductRepository(session)
    sid = uuid4()
    await repo.list_paginated_with_filters(series_id=sid)

    assert len(captured) == 1
    sql = _compile_sql(captured[0])
    assert "products.series_id" in sql


@pytest.mark.asyncio
async def test_stage3_material_id_filter_emits_equality_clause() -> None:
    session, captured = _fake_session()
    repo = ProductRepository(session)
    mid = uuid4()
    await repo.list_paginated_with_filters(material_id=mid)

    assert len(captured) == 1
    sql = _compile_sql(captured[0])
    assert "products.material_id" in sql


@pytest.mark.asyncio
async def test_stage3_tier_code_filter_emits_join_to_series_tiers() -> None:
    session, captured = _fake_session()
    repo = ProductRepository(session)
    await repo.list_paginated_with_filters(tier_code="platinum")

    assert len(captured) == 1
    sql = _compile_sql(captured[0])
    # Debe correlacionar series con products.series_id y join a series_tiers.code.
    assert "exists" in sql
    assert "series_tiers" in sql
    assert "series_tiers.code" in sql


# ---------------------------------------------------------------------------
# Combinación con filtros existentes: no rompe + clauses acumulan.
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_stage3_filters_combined_with_legacy_filters() -> None:
    session, captured = _fake_session()
    repo = ProductRepository(session)
    sid = uuid4()
    mid = uuid4()
    rows, cursor, total = await repo.list_paginated_with_filters(
        family="valve",
        brand="mt",
        dn="15",
        pn="16",
        division_code="industrial",
        series_id=sid,
        material_id=mid,
        tier_code="gold",
    )
    # Sin DB real, devuelve lista vacía + sin cursor + total None.
    assert rows == []
    assert cursor is None
    assert total is None
    sql = _compile_sql(captured[0])
    # Verificamos presencia de cada filtro.
    for fragment in (
        "products.family",
        "products.brand",
        "products.dn",
        "products.pn",
        "products.series_id",
        "products.material_id",
        "exists",
        "series_tiers",
        "product_divisions",
    ):
        assert fragment in sql, f"missing fragment {fragment!r} in compiled SQL"


@pytest.mark.asyncio
async def test_stage3_kwargs_default_none_no_extra_clauses() -> None:
    """Sin kwargs Stage 3 — la query NO debe contener EXISTS sobre product_divisions
    ni references a series_tiers (back-compat)."""
    session, captured = _fake_session()
    repo = ProductRepository(session)
    await repo.list_paginated_with_filters(family="valve")

    sql = _compile_sql(captured[0])
    assert "product_divisions" not in sql
    assert "series_tiers" not in sql


@pytest.mark.asyncio
async def test_stage3_filters_signature_kwargs_only() -> None:
    """Los nuevos parámetros deben ser keyword-only (firma del repo)."""
    import inspect
    sig = inspect.signature(ProductRepository.list_paginated_with_filters)
    for name in ("division_code", "series_id", "material_id", "tier_code"):
        assert name in sig.parameters, f"missing kwarg {name!r}"
        assert sig.parameters[name].kind == inspect.Parameter.KEYWORD_ONLY
        assert sig.parameters[name].default is None


@pytest.mark.asyncio
async def test_stage3_uuid_type_accepted_for_series_and_material() -> None:
    session, captured = _fake_session()
    repo = ProductRepository(session)
    sid: UUID = uuid4()
    mid: UUID = uuid4()
    # Ambos son UUID — no debe lanzar.
    await repo.list_paginated_with_filters(series_id=sid, material_id=mid)
    assert len(captured) == 1
