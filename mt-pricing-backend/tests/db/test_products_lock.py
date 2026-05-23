"""US-1A-02-10 — DoD: trigger soft-delete + manual_locked_fields gap.

Valida:
- DELETE físico en products lanza EXCEPTION (trigger raise_use_soft_delete).
- UPDATE active=false (soft-deactivate) sigue funcionando.
- Columna `manual_locked_fields` existe con default `'{}'::text[]` y NOT NULL.
- Append a manual_locked_fields persiste via array operators.
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
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


_INSERT_PRODUCT_SQL = """
    INSERT INTO products (sku, family, brand_id, family_id)
    SELECT :sku, :family,
           (SELECT id FROM brands WHERE code = 'default'),
           (SELECT id FROM families WHERE code = 'default')
    ON CONFLICT (sku) DO NOTHING
"""


# --------------------------------------------------------------------------
# Soft-delete trigger
# --------------------------------------------------------------------------
async def test_delete_product_blocked_by_trigger(db_session: AsyncSession) -> None:
    """DELETE en products lanza exception con mensaje explicativo."""
    from sqlalchemy.exc import DBAPIError

    await db_session.execute(
        text(_INSERT_PRODUCT_SQL),
        {"sku": "LOCK-V-001", "family": "gate_valve"},
    )
    await db_session.flush()

    with pytest.raises(DBAPIError) as exc_info:
        await db_session.execute(text("DELETE FROM products WHERE sku = 'LOCK-V-001';"))
        await db_session.flush()

    # El mensaje del trigger debe mencionar 'soft-deactivate' o 'VAT'.
    msg = str(exc_info.value).lower()
    assert "soft" in msg or "vat" in msg or "delete físico" in msg


async def test_soft_deactivate_product_works(db_session: AsyncSession) -> None:
    """UPDATE active=false (soft-delete pattern) sigue funcionando normalmente."""
    await db_session.execute(
        text(_INSERT_PRODUCT_SQL),
        {"sku": "LOCK-V-002", "family": "ball_valve"},
    )
    await db_session.flush()

    await db_session.execute(
        text("UPDATE products SET lifecycle_status = 'deprecated' WHERE sku = 'LOCK-V-002';")
    )
    await db_session.flush()

    row = await db_session.execute(
        text("SELECT lifecycle_status FROM products WHERE sku = 'LOCK-V-002';")
    )
    assert row.scalar_one() == "deprecated"


# --------------------------------------------------------------------------
# manual_locked_fields gap (R-S2-06)
# --------------------------------------------------------------------------
async def test_manual_locked_fields_default_empty_array(db_session: AsyncSession) -> None:
    """Columna manual_locked_fields default '{}'::text[] (array vacío, NOT NULL)."""
    await db_session.execute(
        text(_INSERT_PRODUCT_SQL),
        {"sku": "LOCK-V-003", "family": "gate_valve"},
    )
    await db_session.flush()

    row = await db_session.execute(
        text("SELECT manual_locked_fields FROM products WHERE sku = 'LOCK-V-003';")
    )
    assert row.scalar_one() == []


async def test_manual_locked_fields_append_and_query(db_session: AsyncSession) -> None:
    """Append valores a manual_locked_fields persiste y array operators funcionan."""
    await db_session.execute(
        text(
            """
            INSERT INTO products (sku, family, manual_locked_fields, brand_id, family_id)
            SELECT 'LOCK-V-004', 'gate_valve', ARRAY['name_en','description_en']::text[],
                   (SELECT id FROM brands WHERE code = 'default'),
                   (SELECT id FROM families WHERE code = 'default')
            """
        )
    )
    await db_session.flush()

    row = await db_session.execute(
        text("SELECT manual_locked_fields FROM products WHERE sku = 'LOCK-V-004';")
    )
    locked = row.scalar_one()
    assert set(locked) == {"name_en", "description_en"}

    # Query: productos con 'name_en' bloqueado.
    count_row = await db_session.execute(
        text("SELECT count(*) FROM products WHERE 'name_en' = ANY(manual_locked_fields);")
    )
    assert count_row.scalar_one() >= 1


async def test_manual_locked_fields_not_null_constraint(db_session: AsyncSession) -> None:
    """Intentar INSERT con manual_locked_fields=NULL falla (columna NOT NULL)."""
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        await db_session.execute(
            text(
                """
                INSERT INTO products (sku, family, manual_locked_fields, brand_id, family_id)
                SELECT 'LOCK-V-005', 'gate_valve', NULL,
                       (SELECT id FROM brands WHERE code = 'default'),
                       (SELECT id FROM families WHERE code = 'default')
                """
            )
        )
        await db_session.flush()
