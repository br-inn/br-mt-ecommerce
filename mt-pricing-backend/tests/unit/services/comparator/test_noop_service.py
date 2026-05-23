"""Tests del :class:`NoopComparatorService` (ADR-012 hooks Fase 1)."""

from __future__ import annotations

import logging
from uuid import uuid4

import pytest

from app.services.comparator.interfaces import ComparisonStats
from app.services.comparator.noop_service import (
    DISABLED_WARNING,
    NoopComparatorService,
)

pytestmark = pytest.mark.unit


@pytest.fixture
def service() -> NoopComparatorService:
    return NoopComparatorService()


async def test_find_candidates_returns_empty_and_warns(
    service: NoopComparatorService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="app.services.comparator.noop_service")
    result = await service.find_candidates(product_sku="SKU-001", limit=5)
    assert result == []
    assert any(DISABLED_WARNING in r.message for r in caplog.records)


async def test_confirm_match_is_noop_and_warns(
    service: NoopComparatorService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="app.services.comparator.noop_service")
    listing_id = uuid4()
    decided_by = uuid4()
    result = await service.confirm_match(
        listing_id=listing_id,
        product_sku="SKU-001",
        decided_by=decided_by,
        evidence={"foo": "bar"},
    )
    assert result is None
    assert any(DISABLED_WARNING in r.message for r in caplog.records)
    # Verifica que el extra propaga la op
    confirm_records = [r for r in caplog.records if getattr(r, "op", None) == "confirm_match"]
    assert confirm_records, "no se loggeó WARNING con op=confirm_match"


async def test_reject_match_is_noop_and_warns(
    service: NoopComparatorService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="app.services.comparator.noop_service")
    result = await service.reject_match(
        listing_id=uuid4(),
        product_sku="SKU-002",
        decided_by=uuid4(),
    )
    assert result is None
    reject_records = [r for r in caplog.records if getattr(r, "op", None) == "reject_match"]
    assert reject_records


async def test_get_stats_returns_zeros_and_warns(
    service: NoopComparatorService, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.WARNING, logger="app.services.comparator.noop_service")
    stats = await service.get_stats()
    assert isinstance(stats, ComparisonStats)
    assert stats.listings_total == 0
    assert stats.listings_with_match == 0
    assert stats.decisions_pending == 0
    assert stats.decisions_confirmed == 0
    assert stats.decisions_rejected == 0
    assert any(DISABLED_WARNING in r.message for r in caplog.records)
