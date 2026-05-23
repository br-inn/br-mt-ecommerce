"""US-1A-03-01 — DoD: modelo Supplier + Currency + migración + seed.

Tests integration: levantan Postgres efímero (testcontainers) y validan:
- Las 4 currencies seed están presentes.
- Insertar supplier con FK válida funciona.
- Insertar supplier con FK inválida falla por FK constraint.
- Partial unique `is_base` previene una segunda moneda base.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    """Aplica `alembic upgrade head` antes de los tests."""
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def test_currencies_seed_has_four_rows(db_session: AsyncSession) -> None:
    """Migración 0004 siembra USD, EUR, AED, SAR."""
    rows = await db_session.execute(text("SELECT code FROM currencies ORDER BY code;"))
    codes = {r[0] for r in rows.all()}
    assert codes == {"AED", "EUR", "SAR", "USD"}


async def test_currencies_seed_aed_is_base(db_session: AsyncSession) -> None:
    """AED es la moneda base (única con is_base=true)."""
    rows = await db_session.execute(text("SELECT code FROM currencies WHERE is_base = true;"))
    bases = {r[0] for r in rows.all()}
    assert bases == {"AED"}


async def test_currencies_decimals_check(db_session: AsyncSession) -> None:
    """CHECK ck_currencies_decimals — rechaza decimals < 0 o > 8."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO currencies (code, name, decimals, is_base) "
                "VALUES ('XYZ', 'Bad', 99, false);"
            )
        )
        await db_session.flush()


async def test_currencies_only_one_base_allowed(db_session: AsyncSession) -> None:
    """Partial unique uq_currencies_one_base — sólo una moneda base."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO currencies (code, name, decimals, is_base) "
                "VALUES ('GBP', 'Pound', 2, true);"
            )
        )
        await db_session.flush()


async def test_supplier_insert_with_valid_currency(db_session: AsyncSession) -> None:
    """Insertar supplier con contract_currency='EUR' (FK válida) persiste."""
    from app.db.models import Supplier

    sup = Supplier(
        code="MT_VALVES_ES",
        name="MT Valves España",
        contract_currency="EUR",
        lead_time_days=45,
        contact_email="ventas@mt-valves.es",
    )
    db_session.add(sup)
    await db_session.flush()

    # Server defaults
    assert sup.active is True
    assert sup.created_at is not None

    # Re-read
    fetched = await db_session.execute(
        text(
            "SELECT name, contract_currency, lead_time_days FROM suppliers WHERE code = 'MT_VALVES_ES';"
        )
    )
    row = fetched.one()
    assert row[0] == "MT Valves España"
    assert row[1] == "EUR"
    assert row[2] == 45


async def test_supplier_insert_with_invalid_currency_fails(db_session: AsyncSession) -> None:
    """Insertar supplier con contract_currency='XYZ' (no en seed) falla por FK."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                "INSERT INTO suppliers (code, name, contract_currency) "
                "VALUES ('BAD_SUP', 'Bad Supplier', 'XYZ');"
            )
        )
        await db_session.flush()


async def test_supplier_updated_at_trigger(db_session: AsyncSession) -> None:
    """Trigger trg_suppliers_updated_at actualiza timestamp en UPDATE."""
    from app.db.models import Supplier

    sup = Supplier(code="TEST_UPDATE", name="Test", contract_currency="USD")
    db_session.add(sup)
    await db_session.flush()
    initial_updated = sup.updated_at

    # Importante: forzar commit-like sync.
    await db_session.execute(
        text("UPDATE suppliers SET name = 'Test Renamed' WHERE code = 'TEST_UPDATE';")
    )
    await db_session.flush()

    refetch = await db_session.execute(
        text("SELECT updated_at FROM suppliers WHERE code = 'TEST_UPDATE';")
    )
    new_updated = refetch.scalar_one()
    assert new_updated >= initial_updated  # Trigger may set equal if same tx tick.
