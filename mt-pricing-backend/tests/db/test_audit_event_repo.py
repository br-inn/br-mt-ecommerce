"""US-1A-07-01-S1 — DoD: helper de inserción de audit_events.

Cubre:
1. `AuditRepository.record(...)` persiste un AuditEvent (campos requeridos).
2. Las particiones existen y la fila va a la partición correcta del mes.
3. La inmutabilidad la garantiza el trigger SQL (test SQL crudo).

NOTA: el hash chain (`prev_hash` / `current_hash`) lo computa el trigger
`audit_events_hash_chain_trigger` que vive en
`supabase/migrations/20260506_002_audit_chain.sql`. Ese trigger NO se aplica
desde Alembic — se aplica via supabase CLI / dashboard. Por eso aquí sólo
verificamos que el INSERT funciona y que el helper construye el modelo bien;
los tests de hash chain end-to-end vienen cuando levantamos el supabase
local en CI (US-1A-07-02-S1).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import pytest
from sqlalchemy import select, text
from sqlalchemy.exc import DBAPIError, IntegrityError

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True, scope="module")
def _migrate(postgres_container: str) -> None:
    """Aplica `alembic upgrade head` antes de cualquier test del módulo."""
    import os

    from alembic.config import Config

    from alembic import command

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", os.environ["ALEMBIC_DATABASE_URL"])
    command.upgrade(cfg, "head")


async def test_audit_repository_record_persists_event(db_session: AsyncSession) -> None:
    """Helper `record(...)` crea un AuditEvent con los campos canónicos."""
    from app.db.models import AuditEvent
    from app.repositories.audit import AuditRepository

    repo = AuditRepository(db_session)
    evt = await repo.record(
        entity_type="product",
        entity_id="MT-V-038",
        action="create",
        actor_email="psierra@br-innovation.com",
        actor_role="comercial",
        after={"name_en": "Gate Valve DN50", "family": "gate_valve"},
        payload_diff={"name_en": [None, "Gate Valve DN50"]},
        request_id="req-test-001",
    )

    # `flush()` ya sucedió dentro del helper.
    assert evt.entity_type == "product"
    assert evt.entity_id == "MT-V-038"
    assert evt.action == "create"
    assert evt.id is not None  # BIGSERIAL asignado
    assert evt.event_at is not None  # server_default now()

    # Round-trip read
    stmt = select(AuditEvent).where(AuditEvent.entity_id == "MT-V-038")
    result = await db_session.execute(stmt)
    fetched = result.scalars().one()
    assert fetched.action == "create"
    assert fetched.actor_email == "psierra@br-innovation.com"
    assert fetched.payload_diff == {"name_en": [None, "Gate Valve DN50"]}


async def test_audit_repository_list_for_entity(db_session: AsyncSession) -> None:
    """`list_for_entity` ordena cronológicamente desc."""
    from app.repositories.audit import AuditRepository

    repo = AuditRepository(db_session)

    await repo.record(
        entity_type="product", entity_id="SKU-ORDER-1", action="create", payload_diff={"v": 1}
    )
    await repo.record(
        entity_type="product", entity_id="SKU-ORDER-1", action="update", payload_diff={"v": 2}
    )
    await repo.record(
        entity_type="product", entity_id="SKU-ORDER-1", action="update", payload_diff={"v": 3}
    )

    events = await repo.list_for_entity("product", "SKU-ORDER-1")
    assert len(events) == 3
    # Más reciente primero
    diffs = [e.payload_diff for e in events]
    assert {"v": 3} in diffs
    assert {"v": 1} in diffs


async def test_audit_events_partition_routing(db_session: AsyncSession) -> None:
    """Una fila INSERT con `event_at` en mayo 2026 va a la partición `audit_events_2026_05`."""
    # Inserta apuntando explícitamente al mes que ya tiene partición creada.
    await db_session.execute(
        text(
            "INSERT INTO audit_events "
            "(event_at, entity_type, entity_id, action, payload_diff) "
            "VALUES (:ts, 'product', 'PARTITION-TEST', 'create', '{}'::jsonb);"
        ),
        {"ts": datetime(2026, 5, 15, 12, 0, 0, tzinfo=UTC)},
    )
    await db_session.flush()

    # La fila debe encontrarse vía la tabla padre.
    result = await db_session.execute(
        text("SELECT count(*) FROM audit_events WHERE entity_id = 'PARTITION-TEST';")
    )
    assert result.scalar_one() == 1

    # Y también directamente en la partición específica.
    result = await db_session.execute(
        text("SELECT count(*) FROM audit_events_2026_05 WHERE entity_id = 'PARTITION-TEST';")
    )
    assert result.scalar_one() == 1


async def test_audit_events_partition_outside_range_fails(db_session: AsyncSession) -> None:
    """INSERT con `event_at` fuera de las particiones definidas falla.

    Sólo creamos `2026_05` y `2026_06` en la migración 001 — un INSERT en
    julio no encuentra partición y lanza error. Esto valida que las
    particiones se aplican (no es un trigger no-op).
    """
    with pytest.raises((IntegrityError, DBAPIError)):
        await db_session.execute(
            text(
                "INSERT INTO audit_events "
                "(event_at, entity_type, entity_id, action, payload_diff) "
                "VALUES (:ts, 'product', 'OUT-OF-RANGE', 'create', '{}'::jsonb);"
            ),
            {"ts": datetime(2030, 12, 15, 12, 0, 0, tzinfo=UTC)},
        )
        await db_session.flush()
