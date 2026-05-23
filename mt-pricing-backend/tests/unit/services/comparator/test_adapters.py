"""Tests para los tres comparator adapters (US-RND-01-11 / FR-CMP-GRAPH-01).

AC verificados:
  AC-1: ComparatorService con RagOnlyComparatorAdapter activo + stubs Hybrid
        y FullGraphRag.
  AC-3: Swap de adapter vía COMPARATOR_ADAPTER sin cambiar endpoints.
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from app.services.comparator.adapters import (
    FullGraphRagComparatorAdapter,
    HybridComparatorAdapter,
    RagOnlyComparatorAdapter,
)
from app.services.comparator.interfaces import ComparisonStats, ComparatorPort

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _all_adapters() -> list[tuple[str, ComparatorPort]]:
    return [
        ("rag_only", RagOnlyComparatorAdapter()),
        ("hybrid", HybridComparatorAdapter()),
        ("full_graph_rag", FullGraphRagComparatorAdapter()),
    ]


# ---------------------------------------------------------------------------
# AC-1 — todos los adapters implementan ComparatorPort
# ---------------------------------------------------------------------------


def test_rag_only_implements_comparator_port() -> None:
    assert isinstance(RagOnlyComparatorAdapter(), ComparatorPort)


def test_hybrid_implements_comparator_port() -> None:
    assert isinstance(HybridComparatorAdapter(), ComparatorPort)


def test_full_graph_rag_implements_comparator_port() -> None:
    assert isinstance(FullGraphRagComparatorAdapter(), ComparatorPort)


# ---------------------------------------------------------------------------
# RagOnlyComparatorAdapter — activo Fase 1
# ---------------------------------------------------------------------------


async def test_rag_only_find_candidates_returns_empty() -> None:
    adapter = RagOnlyComparatorAdapter()
    result = await adapter.find_candidates(product_sku="SKU-001", limit=5)
    assert result == []


async def test_rag_only_confirm_match_is_noop() -> None:
    adapter = RagOnlyComparatorAdapter()
    result = await adapter.confirm_match(
        listing_id=uuid4(),
        product_sku="SKU-001",
        decided_by=uuid4(),
    )
    assert result is None


async def test_rag_only_reject_match_is_noop() -> None:
    adapter = RagOnlyComparatorAdapter()
    result = await adapter.reject_match(
        listing_id=uuid4(),
        product_sku="SKU-001",
        decided_by=uuid4(),
    )
    assert result is None


async def test_rag_only_get_stats_returns_zeros() -> None:
    adapter = RagOnlyComparatorAdapter()
    stats = await adapter.get_stats()
    assert isinstance(stats, ComparisonStats)
    assert stats.listings_total == 0
    assert stats.listings_with_match == 0
    assert stats.decisions_pending == 0
    assert stats.decisions_confirmed == 0
    assert stats.decisions_rejected == 0


# ---------------------------------------------------------------------------
# HybridComparatorAdapter — stub Fase 2 (NotImplementedError)
# ---------------------------------------------------------------------------


async def test_hybrid_find_candidates_raises() -> None:
    adapter = HybridComparatorAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.find_candidates(product_sku="SKU-001")


async def test_hybrid_confirm_match_raises() -> None:
    adapter = HybridComparatorAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.confirm_match(listing_id=uuid4(), product_sku="SKU-001", decided_by=uuid4())


async def test_hybrid_reject_match_raises() -> None:
    adapter = HybridComparatorAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.reject_match(listing_id=uuid4(), product_sku="SKU-001", decided_by=uuid4())


async def test_hybrid_get_stats_raises() -> None:
    adapter = HybridComparatorAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.get_stats()


# ---------------------------------------------------------------------------
# FullGraphRagComparatorAdapter — stub Fase 2+ (NotImplementedError)
# ---------------------------------------------------------------------------


async def test_full_graph_rag_find_candidates_raises() -> None:
    adapter = FullGraphRagComparatorAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.find_candidates(product_sku="SKU-001")


async def test_full_graph_rag_confirm_match_raises() -> None:
    adapter = FullGraphRagComparatorAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.confirm_match(listing_id=uuid4(), product_sku="SKU-001", decided_by=uuid4())


async def test_full_graph_rag_reject_match_raises() -> None:
    adapter = FullGraphRagComparatorAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.reject_match(listing_id=uuid4(), product_sku="SKU-001", decided_by=uuid4())


async def test_full_graph_rag_get_stats_raises() -> None:
    adapter = FullGraphRagComparatorAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.get_stats()
