"""Best practices DB — verifica índices FK, índices parciales, RLS wrapping y repos.

Usa testcontainers + alembic upgrade head (patrón de tests/db/test_rls_finas.py).
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import text

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
async def _index_exists(session, index_name: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM pg_indexes WHERE indexname = :n"),
        {"n": index_name},
    )
    return result.scalar() is not None


# ---------------------------------------------------------------------------
# Task 1 — FK indexes on products
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_products_fk_indexes_exist(db_session):
    """Las FKs de products tienen índices explícitos."""
    expected = [
        "idx_products_brand_id",
        "idx_products_family_id",
        "idx_products_subfamily_id",
        "idx_products_type_id",
        "idx_products_series_id",
        "idx_products_material_id",
        "idx_products_parent_sku",
        "idx_products_display_pair_sku",
        "idx_products_created_by",
        "idx_products_updated_by",
    ]
    missing = [n for n in expected if not await _index_exists(db_session, n)]
    assert not missing, f"Índices FK faltantes en products: {missing}"


# ---------------------------------------------------------------------------
# Task 2 — Partial indexes
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_products_partial_indexes_exist(db_session):
    """Partial indexes en products para el hot path deleted_at IS NULL."""
    expected = [
        "idx_products_active_lifecycle",
        "idx_products_family_not_deleted",
    ]
    missing = [n for n in expected if not await _index_exists(db_session, n)]
    assert not missing, f"Partial indexes faltantes: {missing}"


# ---------------------------------------------------------------------------
# Task 3 — RLS wrapping (contrato funcional)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_rls_comercial_cannot_read_audit(db_session):
    """Comercial no debe ver filas de audit_events (RLS finas)."""
    await db_session.execute(text("SET LOCAL app.user_role = 'comercial'"))
    await db_session.execute(text("SET LOCAL ROLE mt_app"))
    result = await db_session.execute(text("SELECT count(*) FROM audit_events"))
    count = result.scalar()
    assert count == 0, "Comercial no debe ver audit_events"


@pytest.mark.asyncio
async def test_rls_products_comercial_can_read(db_session):
    """Comercial sí puede leer products (RLS finas)."""
    await db_session.execute(text("SET LOCAL app.user_role = 'comercial'"))
    await db_session.execute(text("SET LOCAL ROLE mt_app"))
    # No esperamos error — solo que la query devuelva sin exception
    result = await db_session.execute(text("SELECT count(*) FROM products"))
    assert result.scalar() >= 0


# ---------------------------------------------------------------------------
# Task 4 — FTS GIN fix
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_fts_gin_obsolete_removed(db_session):
    """ix_products_fts_gin (referencia name_en dropeada) no debe existir."""
    assert not await _index_exists(db_session, "ix_products_fts_gin"), (
        "ix_products_fts_gin referencia name_en (mig 065 dropped) — debe haberse dropeado"
    )


@pytest.mark.asyncio
async def test_fts_trgm_index_on_translations(db_session):
    """GIN trgm index en product_translations.name WHERE lang='en' existe."""
    assert await _index_exists(db_session, "idx_pt_name_en_trgm"), (
        "Falta GIN trgm index para búsqueda de similaridad en product_translations"
    )


# ---------------------------------------------------------------------------
# Task 7 — idle_in_transaction timeout
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_idle_in_transaction_timeout_configured(db_session):
    """El timeout de transacciones idle debe estar configurado en la sesión."""
    result = await db_session.execute(
        text("SHOW idle_in_transaction_session_timeout")
    )
    val = result.scalar()
    assert val != "0", (
        f"idle_in_transaction_session_timeout es '0' (deshabilitado). "
        f"Valor actual: {val!r}"
    )
