"""Tests de integración de los repos del agente de validación.

Requiere testcontainers (Postgres efímero con migraciones Alembic aplicadas).
Marca: @pytest.mark.integration
"""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.match_agent import MatchAgentConfig
from app.repositories.match_agent import (
    MatchAgentConfigRepository,
    MatchAgentDecisionRepository,
)

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def seeded_config(db_session: AsyncSession) -> MatchAgentConfig:
    """Inserta la fila singleton id=1 si no existe."""
    row = await db_session.get(MatchAgentConfig, 1)
    if row is None:
        row = MatchAgentConfig(id=1, mode="shadow")
        db_session.add(row)
        await db_session.flush()
    return row


@pytest_asyncio.fixture
async def match_candidate_id(db_session: AsyncSession) -> uuid.UUID:
    """Retorna un UUID ficticio sin FK real (match_candidates vacía en tests)."""
    # La FK tiene ondelete=CASCADE pero podemos desactivar FK checks en Postgres
    # o insertar directamente un candidato de prueba.
    # Insertamos un candidato mínimo para satisfacer la FK.
    # Necesitamos un product_sku que exista en products ó desactivar FK.
    # Usamos DEFERRABLE + SET CONSTRAINTS DEFERRED si está disponible;
    # si no, creamos un candidato con un sku cualquiera deshabilitando FK checks.
    # La alternativa más portable: insertar directamente con text() y SET LOCAL.
    from sqlalchemy import text

    from app.db.models.match_candidate import MatchCandidate

    await db_session.execute(text("SET LOCAL session_replication_role = 'replica'"))

    candidate_id = uuid.uuid4()
    candidate = MatchCandidate(
        id=candidate_id,
        product_sku="TEST-SKU-AGENT",
        channel="amazon_uae",
        external_id="EXT-TEST-001",
        title="Test product",
        brand=None,
        price_aed=__import__("decimal").Decimal("100.00"),
        delivery_text=None,
        specs_jsonb={},
        kind="peer",
        score=80,
    )
    db_session.add(candidate)
    await db_session.flush()
    return candidate_id


# ---------------------------------------------------------------------------
# MatchAgentConfigRepository
# ---------------------------------------------------------------------------


async def test_get_config_returns_singleton(
    db_session: AsyncSession, seeded_config: MatchAgentConfig
) -> None:
    repo = MatchAgentConfigRepository(db_session)
    cfg = await repo.get()
    assert cfg is not None
    assert cfg.id == 1
    assert cfg.mode == "shadow"


async def test_update_config_changes_mode(
    db_session: AsyncSession, seeded_config: MatchAgentConfig
) -> None:
    repo = MatchAgentConfigRepository(db_session)
    updated = await repo.update(mode="active", updated_by=None)
    assert updated.mode == "active"


# ---------------------------------------------------------------------------
# MatchAgentDecisionRepository
# ---------------------------------------------------------------------------


async def test_count_decisions_empty(db_session: AsyncSession) -> None:
    repo = MatchAgentDecisionRepository(db_session)
    assert await repo.count_shadow() == 0


async def test_record_decision(db_session: AsyncSession, match_candidate_id: uuid.UUID) -> None:
    repo = MatchAgentDecisionRepository(db_session)
    decision = await repo.record(
        candidate_id=match_candidate_id,
        product_sku="TEST-SKU-AGENT",
        verdict="auto_validate",
        mode="shadow",
        applied=False,
        signal="conformal",
        score=90,
    )
    assert decision.id is not None
    assert decision.verdict == "auto_validate"
    assert decision.mode == "shadow"


async def test_count_shadow_after_record(
    db_session: AsyncSession, match_candidate_id: uuid.UUID
) -> None:
    repo = MatchAgentDecisionRepository(db_session)
    await repo.record(
        candidate_id=match_candidate_id,
        product_sku="TEST-SKU-AGENT",
        verdict="auto_validate",
        mode="shadow",
        applied=False,
        signal="conformal",
        score=90,
    )
    assert await repo.count_shadow() == 1


async def test_latest_for_candidate(
    db_session: AsyncSession, match_candidate_id: uuid.UUID
) -> None:
    repo = MatchAgentDecisionRepository(db_session)
    await repo.record(
        candidate_id=match_candidate_id,
        product_sku="TEST-SKU-AGENT",
        verdict="auto_discard",
        mode="shadow",
        applied=False,
        signal="bootstrap",
        score=20,
    )
    latest = await repo.latest_for_candidate(match_candidate_id)
    assert latest is not None
    assert latest.candidate_id == match_candidate_id
    assert latest.verdict == "auto_discard"


async def test_set_human_outcome(db_session: AsyncSession, match_candidate_id: uuid.UUID) -> None:
    repo = MatchAgentDecisionRepository(db_session)
    await repo.record(
        candidate_id=match_candidate_id,
        product_sku="TEST-SKU-AGENT",
        verdict="auto_validate",
        mode="shadow",
        applied=False,
        signal="conformal",
        score=88,
    )
    await repo.set_human_outcome(match_candidate_id, "validated")
    latest = await repo.latest_for_candidate(match_candidate_id)
    assert latest is not None
    assert latest.human_outcome == "validated"


async def test_shadow_precision_with_data(
    db_session: AsyncSession, match_candidate_id: uuid.UUID
) -> None:
    repo = MatchAgentDecisionRepository(db_session)
    decision = await repo.record(
        candidate_id=match_candidate_id,
        product_sku="TEST-SKU-AGENT",
        verdict="auto_validate",
        mode="shadow",
        applied=False,
        signal="conformal",
        score=88,
    )
    decision.human_outcome = "validated"
    await db_session.flush()

    count, precision = await repo.shadow_precision()
    assert count == 1
    assert precision == 1.0


async def test_shadow_precision_empty(db_session: AsyncSession) -> None:
    repo = MatchAgentDecisionRepository(db_session)
    count, precision = await repo.shadow_precision()
    assert count == 0
    assert precision is None
