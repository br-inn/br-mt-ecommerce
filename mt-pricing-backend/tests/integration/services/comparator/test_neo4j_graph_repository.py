"""Tests de integración para Neo4jGraphRepository con Neo4j real.

US-F15-01-04 — Sprint 10 Wave 4.

Requiere Neo4j local corriendo (bolt://localhost:17687).
Ejecutar con: pytest -m neo4j_real tests/integration/services/comparator/
"""
from __future__ import annotations

import pytest
from uuid import uuid4

pytestmark = pytest.mark.neo4j_real


@pytest.fixture
def neo4j_repo(neo4j_driver):
    from app.services.graphrag.adapters.neo4j_real import Neo4jGraphStore
    from app.services.comparator.graph_repository import Neo4jGraphRepository

    store = Neo4jGraphStore(neo4j_driver, database="neo4j")
    return Neo4jGraphRepository(graph_store=store)


@pytest.mark.asyncio
async def test_health_check_returns_true(neo4j_repo):
    result = await neo4j_repo.health_check()
    assert result["healthy"] is True
    assert result["backend"] == "neo4j_graph_repository"
    assert "store_health" in result


@pytest.mark.asyncio
async def test_get_product_neighbors_empty_for_unknown_sku(neo4j_repo):
    neighbors = await neo4j_repo.get_product_neighbors("UNKNOWN-SKU-99999")
    assert isinstance(neighbors, list)
    assert len(neighbors) == 0


@pytest.mark.asyncio
async def test_get_competitor_context_empty_for_unknown(neo4j_repo):
    ctx = await neo4j_repo.get_competitor_context(uuid4())
    assert ctx["graph_confidence"] == 0.0
    assert isinstance(ctx["product_matches"], list)
    assert isinstance(ctx["supplier_hints"], list)
    assert "competitor_listing_id" in ctx


@pytest.mark.asyncio
async def test_health_check_none_graph_store():
    from app.services.comparator.graph_repository import Neo4jGraphRepository

    repo = Neo4jGraphRepository(graph_store=None)
    result = await repo.health_check()
    assert result["healthy"] is False
    assert result["backend"] == "neo4j_graph_repository"
    assert "note" in result
