"""Validar/descartar deben escribir golden_labels + label + human_outcome."""
from __future__ import annotations

import decimal
import uuid

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from app.db.models.match_candidate import MatchCandidate

pytestmark = pytest.mark.integration


# ---------------------------------------------------------------------------
# Fixture: make_candidate
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def make_candidate(db_session: AsyncSession):
    """Factory que inserta un MatchCandidate sin FK real (session_replication_role=replica)."""

    async def _factory(*, score: int = 80) -> MatchCandidate:
        await db_session.execute(text("SET LOCAL session_replication_role = 'replica'"))
        candidate_id = uuid.uuid4()
        candidate = MatchCandidate(
            id=candidate_id,
            product_sku="TEST-SKU-GOLDEN",
            channel="amazon_uae",
            external_id=f"EXT-GOLDEN-{candidate_id.hex[:8]}",
            title="Test product for golden labels",
            brand=None,
            price_aed=decimal.Decimal("100.00"),
            delivery_text=None,
            specs_jsonb={},
            kind="peer",
            score=score,
        )
        db_session.add(candidate)
        await db_session.flush()
        return candidate

    return _factory


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_validate_writes_golden_label(db_session: AsyncSession, make_candidate) -> None:
    from app.repositories.golden_labels import GoldenLabelRepository
    from app.services.matching.match_service import MatchService

    cand = await make_candidate(score=80)
    service = MatchService(db_session, fetchers=[])
    await service.validate_candidate(cand.id, user_id=None)
    labels = await GoldenLabelRepository(db_session).list_for_training()
    matching = [lb for lb in labels if lb.candidate_id == cand.id]
    assert len(matching) == 1
    assert matching[0].label == 1
    await db_session.refresh(cand)
    assert cand.label == "accept"


async def test_discard_writes_reject_golden_label(db_session: AsyncSession, make_candidate) -> None:
    from app.repositories.golden_labels import GoldenLabelRepository
    from app.services.matching.match_service import MatchService

    cand = await make_candidate(score=20)
    service = MatchService(db_session, fetchers=[])
    await service.discard_candidate(cand.id, reason="tipo incorrecto")
    labels = await GoldenLabelRepository(db_session).list_for_training()
    matching = [lb for lb in labels if lb.candidate_id == cand.id]
    assert len(matching) == 1
    assert matching[0].label == 0
    await db_session.refresh(cand)
    assert cand.label == "reject"
