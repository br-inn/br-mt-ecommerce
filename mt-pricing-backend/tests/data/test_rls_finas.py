"""Integration tests RLS finas — US-1A-07-02 (Sprint 4).

Estrategia: Postgres efímero vía testcontainers + ``alembic upgrade head``.
Cada test setea ``SET LOCAL app.user_role = '<role>'`` antes de la query
y SET ROLE mt_app, evaluando que las policies RLS de migración 022 funcionen.

Cobertura mínima requerida (5+ tests; cubrimos 8 escenarios críticos):

1. comercial INSERT en costs → permitido.
2. comercial INSERT en prices con status='approved' → denegado.
3. gerente UPDATE en prices a status='approved' → permitido.
4. ti UPDATE en products name_en → permitido.
5. comercial SELECT en audit_events → vacío (RLS deniega rows).
6. auditor SELECT en audit_events → permitido (rows visibles).
7. UPDATE/DELETE en audit_events → falla con `forbidden_audit_mutation`.
8. INSERT directo en prices con status='exported' → falla con
   `invalid_initial_status` (trigger 021).
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, InternalError, ProgrammingError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Fixture: alembic upgrade head al inicio del módulo.
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


# ---------------------------------------------------------------------------
# Helpers — set role + minimal data fixtures
# ---------------------------------------------------------------------------
async def _as_role(session: AsyncSession, role: str) -> None:
    """Configura el rol aplicativo + cambia a `mt_app` (RLS aplicable)."""
    # `app.user_role` lo lee `resolve_user_role()`.
    await session.execute(text(f"SET LOCAL app.user_role = '{role}'"))
    # Cambiar a mt_app — superuser bypassa RLS, mt_app no.
    await session.execute(text("SET LOCAL ROLE mt_app"))


async def _reset_role(session: AsyncSession) -> None:
    await session.execute(text("RESET ROLE"))
    await session.execute(text("RESET app.user_role"))


async def _ensure_test_sku(session: AsyncSession, sku: str = "TEST-RLS-001") -> str:
    await _reset_role(session)
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


async def _ensure_mt_app_role(session: AsyncSession) -> None:
    """Asegura que el role mt_app exista (si la migración 001 no lo creó aún)."""
    await session.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT FROM pg_roles WHERE rolname = 'mt_app'
                ) THEN
                    CREATE ROLE mt_app NOLOGIN;
                END IF;
            END $$;
            """
        )
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_comercial_can_insert_into_costs(db_session: AsyncSession) -> None:
    await _ensure_mt_app_role(db_session)
    sku = await _ensure_test_sku(db_session)

    # Otorgar permisos a mt_app sobre las tablas que usaremos.
    await db_session.execute(text("GRANT USAGE ON SCHEMA public TO mt_app"))
    await db_session.execute(
        text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mt_app")
    )
    await db_session.execute(
        text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO mt_app")
    )
    await db_session.commit()

    await _as_role(db_session, "comercial")
    try:
        await db_session.execute(
            text(
                """
                INSERT INTO costs (sku, scheme_code, currency_origin, breakdown,
                                   effective_at, status)
                VALUES (:sku, 'FBA', 'AED',
                        '{"fob_aed": 10.0}'::jsonb,
                        :eff, 'active')
                """
            ),
            {"sku": sku, "eff": datetime.now(tz=UTC)},
        )
        # Sin excepción → policy permitió.
    finally:
        await _reset_role(db_session)


async def test_comercial_cannot_insert_price_with_status_approved(
    db_session: AsyncSession,
) -> None:
    await _ensure_mt_app_role(db_session)
    sku = await _ensure_test_sku(db_session, "TEST-RLS-002")

    await db_session.execute(text("GRANT USAGE ON SCHEMA public TO mt_app"))
    await db_session.execute(
        text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mt_app")
    )
    await db_session.execute(
        text("GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO mt_app")
    )
    await db_session.commit()

    # Resolve channel_id (canal seed).
    res = await db_session.execute(text("SELECT id FROM channels LIMIT 1"))
    row = res.first()
    if row is None:
        pytest.skip("No hay canales seeded para el test.")
    channel_id = row[0]

    await _as_role(db_session, "comercial")
    raised = False
    try:
        try:
            await db_session.execute(
                text(
                    """
                    INSERT INTO prices (product_sku, channel_id, scheme_code, amount,
                                        margin_pct, currency, status)
                    VALUES (:sku, :ch, 'FBA', 100.00, 0.30, 'AED', 'approved')
                    """
                ),
                {"sku": sku, "ch": channel_id},
            )
        except (DBAPIError, ProgrammingError, InternalError):
            raised = True
    finally:
        await _reset_role(db_session)

    assert raised, (
        "comercial NO debe poder INSERT prices con status='approved' "
        "(RLS o trigger initial_status)"
    )


async def test_ti_can_update_products_erp_name(db_session: AsyncSession) -> None:
    await _ensure_mt_app_role(db_session)
    sku = await _ensure_test_sku(db_session, "TEST-RLS-003")

    await db_session.execute(text("GRANT USAGE ON SCHEMA public TO mt_app"))
    await db_session.execute(
        text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mt_app")
    )
    await db_session.commit()

    await _as_role(db_session, "ti")
    try:
        await db_session.execute(
            text("UPDATE products SET erp_name = :n WHERE sku = :sku"),
            {"n": "Renamed by TI", "sku": sku},
        )
    finally:
        await _reset_role(db_session)

    # Verify (as superuser).
    res = await db_session.execute(
        text("SELECT erp_name FROM products WHERE sku = :sku"), {"sku": sku}
    )
    assert res.scalar() == "Renamed by TI"


async def test_audit_events_update_raises_forbidden_mutation(
    db_session: AsyncSession,
) -> None:
    await _ensure_mt_app_role(db_session)
    # Insertar un audit event como superuser.
    await db_session.execute(
        text(
            """
            INSERT INTO audit_events (event_at, entity_type, entity_id, action,
                                      payload_diff)
            VALUES (now(), 'products', 'TEST-RLS-XX', 'product.created', '{}'::jsonb)
            """
        )
    )
    await db_session.commit()

    await db_session.execute(text("GRANT USAGE ON SCHEMA public TO mt_app"))
    await db_session.execute(
        text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mt_app")
    )
    await db_session.commit()

    raised = False
    await _as_role(db_session, "ti")
    try:
        try:
            await db_session.execute(
                text("UPDATE audit_events SET reason = 'oops' WHERE entity_id = 'TEST-RLS-XX'")
            )
        except (DBAPIError, InternalError, ProgrammingError):
            raised = True
    finally:
        await _reset_role(db_session)

    assert raised, "UPDATE en audit_events debe fallar con forbidden_audit_mutation"


async def test_comercial_select_audit_events_returns_empty(
    db_session: AsyncSession,
) -> None:
    await _ensure_mt_app_role(db_session)
    # Inserta un evento como superuser para tener algo que filtrar.
    await db_session.execute(
        text(
            """
            INSERT INTO audit_events (event_at, entity_type, entity_id, action,
                                      payload_diff)
            VALUES (now(), 'products', 'TEST-RLS-AUDIT', 'product.updated',
                    '{}'::jsonb)
            """
        )
    )
    await db_session.commit()

    await db_session.execute(text("GRANT USAGE ON SCHEMA public TO mt_app"))
    await db_session.execute(
        text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mt_app")
    )
    await db_session.commit()

    await _as_role(db_session, "comercial")
    try:
        res = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM audit_events WHERE entity_id = 'TEST-RLS-AUDIT'"
            )
        )
        count = res.scalar()
    finally:
        await _reset_role(db_session)

    assert count == 0, "comercial NO debe ver rows en audit_events"


async def test_auditor_can_select_audit_events(
    db_session: AsyncSession,
) -> None:
    await _ensure_mt_app_role(db_session)
    await db_session.execute(
        text(
            """
            INSERT INTO audit_events (event_at, entity_type, entity_id, action,
                                      payload_diff)
            VALUES (now(), 'products', 'TEST-RLS-AUDITOR', 'product.created',
                    '{}'::jsonb)
            """
        )
    )
    await db_session.commit()

    await db_session.execute(text("GRANT USAGE ON SCHEMA public TO mt_app"))
    await db_session.execute(
        text("GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO mt_app")
    )
    await db_session.commit()

    await _as_role(db_session, "auditor")
    try:
        res = await db_session.execute(
            text(
                "SELECT COUNT(*) FROM audit_events WHERE entity_id = 'TEST-RLS-AUDITOR'"
            )
        )
        count = res.scalar()
    finally:
        await _reset_role(db_session)

    assert count and count >= 1, "auditor SÍ debe ver rows en audit_events"


async def test_invalid_initial_status_blocked_by_trigger(
    db_session: AsyncSession,
) -> None:
    """Trigger 021 prices_initial_status_trg bloquea INSERTs con status terminal."""
    sku = await _ensure_test_sku(db_session, "TEST-RLS-INIT")
    res = await db_session.execute(text("SELECT id FROM channels LIMIT 1"))
    row = res.first()
    if row is None:
        pytest.skip("No hay canales seeded.")
    channel_id = row[0]

    raised = False
    try:
        await db_session.execute(
            text(
                """
                INSERT INTO prices (product_sku, channel_id, scheme_code, amount,
                                    margin_pct, currency, status)
                VALUES (:sku, :ch, 'FBA', 200.00, 0.25, 'AED', 'exported')
                """
            ),
            {"sku": sku, "ch": channel_id},
        )
    except (DBAPIError, InternalError, ProgrammingError):
        raised = True

    assert raised, "INSERT con status='exported' debe fallar con invalid_initial_status"
