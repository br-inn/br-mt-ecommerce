"""US-1A-01-08-S1 — DoD: Alembic up/down testeado.

Levanta un Postgres efímero (testcontainers) y ejecuta `upgrade head`,
`downgrade base`, `upgrade head` para validar idempotencia. Cumple los AC
de US-1A-01-08-S1 sobre roundtrip de migraciones.

Marcado `integration` — requiere Docker corriendo. Skip automático si no.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    pass

pytestmark = [pytest.mark.integration]


def _alembic_config(sync_url: str):
    """Configura Alembic apuntando a la URL sync (psycopg) del container."""
    from alembic.config import Config

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", sync_url)
    return cfg


def _run_migration(direction: str, target: str, sync_url: str) -> None:
    """Wrapper sobre `alembic.command.{upgrade,downgrade}`."""
    from alembic import command

    cfg = _alembic_config(sync_url)
    if direction == "upgrade":
        command.upgrade(cfg, target)
    elif direction == "downgrade":
        command.downgrade(cfg, target)
    else:
        raise ValueError(f"Direction inválida: {direction}")


@pytest.fixture(scope="module")
def alembic_sync_url(postgres_container: str) -> str:
    """Devuelve la URL sync (psycopg) — Alembic usa engine síncrono."""
    sync_url = os.environ.get("ALEMBIC_DATABASE_URL", "")
    assert sync_url, "ALEMBIC_DATABASE_URL no setteado por el container fixture"
    return sync_url


def test_alembic_upgrade_head_then_downgrade_then_upgrade(alembic_sync_url: str) -> None:
    """Roundtrip completo: head → base → head sin errores."""
    # Up
    _run_migration("upgrade", "head", alembic_sync_url)

    # Verifica que las tablas centrales existen.
    from sqlalchemy import create_engine, inspect

    engine = create_engine(alembic_sync_url)
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "users" in tables
        assert "products" in tables
        assert "audit_events" in tables
        assert "roles" in tables
    finally:
        engine.dispose()

    # Down (a base — vacía la BD)
    _run_migration("downgrade", "base", alembic_sync_url)

    # Re-up (idempotencia)
    _run_migration("upgrade", "head", alembic_sync_url)

    engine = create_engine(alembic_sync_url)
    try:
        insp = inspect(engine)
        tables = set(insp.get_table_names())
        assert "products" in tables, "Re-upgrade tras downgrade falló"
    finally:
        engine.dispose()


def test_products_constraints_enforced(alembic_sync_url: str, postgres_container: str) -> None:
    """US-1A-02-01-S1 — UNIQUE(sku), NOT NULL(name_en), CHECK(data_quality)."""
    # Asume que el test anterior dejó la BD en `head`. Si no, upgrade.
    _run_migration("upgrade", "head", alembic_sync_url)

    from sqlalchemy import create_engine, text
    from sqlalchemy.exc import IntegrityError

    engine = create_engine(alembic_sync_url)
    try:
        with engine.begin() as conn:
            conn.execute(
                text(
                    "INSERT INTO products (sku, name_en, family) "
                    "VALUES ('TEST-V-001', 'Test Valve', 'gate_valve');"
                )
            )

        # NOT NULL name_en
        with engine.begin() as conn, pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO products (sku, name_en, family) "
                    "VALUES ('TEST-V-002', NULL, 'ball_valve');"
                )
            )

        # UNIQUE sku (PK)
        with engine.begin() as conn, pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO products (sku, name_en, family) "
                    "VALUES ('TEST-V-001', 'Dup', 'gate_valve');"
                )
            )

        # CHECK data_quality (valor inválido)
        with engine.begin() as conn, pytest.raises(IntegrityError):
            conn.execute(
                text(
                    "INSERT INTO products (sku, name_en, family, data_quality) "
                    "VALUES ('TEST-V-003', 'Bad', 'gate_valve', 'NOT_A_VALID_QUALITY');"
                )
            )

        # Cleanup
        with engine.begin() as conn:
            conn.execute(text("DELETE FROM products WHERE sku LIKE 'TEST-V-%';"))
    finally:
        engine.dispose()
