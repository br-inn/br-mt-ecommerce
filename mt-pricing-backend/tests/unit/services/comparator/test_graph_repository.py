"""Tests para GraphRepository (US-RND-01-11 / FR-CMP-GRAPH-01, US-F15-01-04).

AC verificados:
  AC-2: GraphRepository existe con PostgresGraphRepository activo y
        Neo4jGraphRepository implementado.
  AC-3: get_graph_repository() respeta GRAPHRAG_BACKEND sin tocar API.
  US-F15-01-04: Neo4jGraphRepository delegación real a GraphStorePort.
"""

from __future__ import annotations

from unittest.mock import patch
from uuid import uuid4

import pytest

from app.services.comparator.graph_repository import (
    GraphRepository,
    Neo4jGraphRepository,
    PostgresGraphRepository,
    get_graph_repository,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# AC-2 — PostgresGraphRepository activo (hereda GraphRepository)
# ---------------------------------------------------------------------------

def test_postgres_repo_is_graph_repository() -> None:
    repo = PostgresGraphRepository()
    assert isinstance(repo, GraphRepository)


async def test_postgres_repo_get_product_neighbors_returns_empty() -> None:
    repo = PostgresGraphRepository()
    result = await repo.get_product_neighbors("SKU-001")
    assert result == []


async def test_postgres_repo_get_product_neighbors_with_rel_type() -> None:
    repo = PostgresGraphRepository()
    result = await repo.get_product_neighbors("SKU-001", relationship_type="SUPPLIED_BY")
    assert result == []


async def test_postgres_repo_get_competitor_context_returns_dict() -> None:
    repo = PostgresGraphRepository()
    listing_id = uuid4()
    ctx = await repo.get_competitor_context(listing_id)
    assert isinstance(ctx, dict)
    assert ctx["competitor_listing_id"] == str(listing_id)
    assert "product_matches" in ctx
    assert "supplier_hints" in ctx
    assert "graph_confidence" in ctx
    assert ctx["graph_confidence"] == 0.0


async def test_postgres_repo_health_check_healthy() -> None:
    repo = PostgresGraphRepository()
    result = await repo.health_check()
    assert result["healthy"] is True
    assert result["backend"] == "postgres_graph_repository"


# ---------------------------------------------------------------------------
# AC-2 — Neo4jGraphRepository implementado (hereda GraphRepository)
# ---------------------------------------------------------------------------

def test_neo4j_repo_is_graph_repository() -> None:
    repo = Neo4jGraphRepository()
    assert isinstance(repo, GraphRepository)


async def test_neo4j_repo_get_product_neighbors_none_store_returns_empty() -> None:
    """Sin graph_store inyectado → lista vacía (no NotImplementedError)."""
    repo = Neo4jGraphRepository(graph_store=None)
    result = await repo.get_product_neighbors("SKU-001")
    assert result == []


async def test_neo4j_repo_get_competitor_context_none_store_returns_empty() -> None:
    """Sin graph_store inyectado → dict vacío con graph_confidence=0.0."""
    repo = Neo4jGraphRepository(graph_store=None)
    listing_id = uuid4()
    ctx = await repo.get_competitor_context(listing_id)
    assert ctx["graph_confidence"] == 0.0
    assert ctx["product_matches"] == []
    assert ctx["competitor_listing_id"] == str(listing_id)


async def test_neo4j_repo_health_check_none_store_returns_unhealthy() -> None:
    repo = Neo4jGraphRepository(graph_store=None)
    result = await repo.health_check()
    assert result["backend"] == "neo4j_graph_repository"
    assert result["healthy"] is False
    assert "note" in result


# ---------------------------------------------------------------------------
# US-F15-01-04 — Neo4jGraphRepository con mock de GraphStorePort
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_neo4j_get_product_neighbors_calls_query_neighbors() -> None:
    from unittest.mock import MagicMock
    from app.services.graphrag.ports import GraphEdge, GraphNode

    mock_store = MagicMock()
    mock_store.query_neighbors.return_value = [
        (
            GraphEdge(
                src_label="Product", src_pk="A",
                type="COMPATIBLE_WITH",
                dst_label="Material", dst_pk="M1",
            ),
            GraphNode(label="Material", primary_key="M1", properties={}),
        )
    ]

    repo = Neo4jGraphRepository(graph_store=mock_store)
    result = await repo.get_product_neighbors("SKU-001")

    mock_store.query_neighbors.assert_called_once_with(
        "Product", "SKU-001", edge_type=None
    )
    assert len(result) == 1
    assert result[0]["node_type"] == "Material"
    assert result[0]["primary_key"] == "M1"
    assert result[0]["relationship"] == "COMPATIBLE_WITH"


@pytest.mark.asyncio
async def test_neo4j_get_product_neighbors_with_rel_type() -> None:
    from unittest.mock import MagicMock
    from app.services.graphrag.ports import GraphEdge, GraphNode

    mock_store = MagicMock()
    mock_store.query_neighbors.return_value = [
        (
            GraphEdge(
                src_label="Product", src_pk="SKU-002",
                type="SUPPLIED_BY",
                dst_label="Supplier", dst_pk="SUP-1",
            ),
            GraphNode(label="Supplier", primary_key="SUP-1", properties={"name": "Acme"}),
        )
    ]

    repo = Neo4jGraphRepository(graph_store=mock_store)
    result = await repo.get_product_neighbors("SKU-002", relationship_type="SUPPLIED_BY")

    mock_store.query_neighbors.assert_called_once_with(
        "Product", "SKU-002", edge_type="SUPPLIED_BY"
    )
    assert result[0]["relationship"] == "SUPPLIED_BY"
    assert result[0]["properties"] == {"name": "Acme"}


@pytest.mark.asyncio
async def test_neo4j_get_competitor_context_with_matches() -> None:
    from unittest.mock import MagicMock
    from app.services.graphrag.ports import GraphEdge, GraphNode

    listing_id = uuid4()
    mock_store = MagicMock()
    mock_store.query_neighbors.return_value = [
        (
            GraphEdge(
                src_label="CompetitorListing", src_pk=str(listing_id),
                type="MATCHES",
                dst_label="Product", dst_pk="SKU-A",
            ),
            GraphNode(label="Product", primary_key="SKU-A", properties={"name": "Widget"}),
        ),
        (
            GraphEdge(
                src_label="CompetitorListing", src_pk=str(listing_id),
                type="HINT_SUPPLIER",
                dst_label="Supplier", dst_pk="SUP-X",
            ),
            GraphNode(label="Supplier", primary_key="SUP-X", properties={}),
        ),
    ]

    repo = Neo4jGraphRepository(graph_store=mock_store)
    ctx = await repo.get_competitor_context(listing_id)

    assert ctx["competitor_listing_id"] == str(listing_id)
    assert len(ctx["product_matches"]) == 1
    assert ctx["product_matches"][0]["primary_key"] == "SKU-A"
    assert len(ctx["supplier_hints"]) == 1
    assert ctx["supplier_hints"][0]["primary_key"] == "SUP-X"
    # 1 match → confidence = 1/(1+1) = 0.5
    assert ctx["graph_confidence"] == pytest.approx(0.5)


@pytest.mark.asyncio
async def test_neo4j_get_product_neighbors_exception_returns_empty() -> None:
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.query_neighbors.side_effect = RuntimeError("Neo4j timeout")

    repo = Neo4jGraphRepository(graph_store=mock_store)
    result = await repo.get_product_neighbors("SKU-ERR")
    assert result == []


@pytest.mark.asyncio
async def test_neo4j_health_check_delegates_to_store() -> None:
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.health_check.return_value = {
        "backend": "neo4j_real",
        "healthy": True,
        "nodes": 42,
        "edges": 100,
    }

    repo = Neo4jGraphRepository(graph_store=mock_store)
    result = await repo.health_check()

    assert result["healthy"] is True
    assert result["backend"] == "neo4j_graph_repository"
    assert result["store_health"]["nodes"] == 42


@pytest.mark.asyncio
async def test_neo4j_health_check_store_raises_returns_unhealthy() -> None:
    from unittest.mock import MagicMock

    mock_store = MagicMock()
    mock_store.health_check.side_effect = ConnectionError("Bolt refused")

    repo = Neo4jGraphRepository(graph_store=mock_store)
    result = await repo.health_check()

    assert result["healthy"] is False
    assert "error" in result


# ---------------------------------------------------------------------------
# AC-3 — get_graph_repository() respeta GRAPHRAG_BACKEND
# ---------------------------------------------------------------------------

def test_get_graph_repository_default_returns_postgres(monkeypatch: pytest.MonkeyPatch) -> None:
    """GRAPHRAG_BACKEND=stub (default) → PostgresGraphRepository."""
    monkeypatch.setattr(
        "app.services.comparator.graph_repository.get_graph_repository.__wrapped__"
        if hasattr(get_graph_repository, "__wrapped__") else "app.core.config.settings.GRAPHRAG_BACKEND",
        "stub",
        raising=False,
    )
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.GRAPHRAG_BACKEND = "stub"
        repo = get_graph_repository()
    assert isinstance(repo, PostgresGraphRepository)


def test_get_graph_repository_neo4j_returns_neo4j_repo(monkeypatch: pytest.MonkeyPatch) -> None:
    """GRAPHRAG_BACKEND=neo4j → Neo4jGraphRepository."""
    with patch("app.core.config.settings") as mock_settings:
        mock_settings.GRAPHRAG_BACKEND = "neo4j"
        # El factory intenta importar get_default_graph_store — mockeamos
        with patch(
            "app.services.graphrag.adapters.factory.get_default_graph_store",
            return_value=None,
        ):
            repo = get_graph_repository()
    assert isinstance(repo, Neo4jGraphRepository)


def test_get_graph_repository_config_error_falls_back_to_postgres() -> None:
    """Si config no está disponible (tests sin DI), fallback a Postgres."""
    with patch("app.core.config.settings", side_effect=Exception("no config")):
        repo = get_graph_repository()
    assert isinstance(repo, PostgresGraphRepository)
