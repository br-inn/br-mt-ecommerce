"""Tests para GraphRepository (US-RND-01-11 / FR-CMP-GRAPH-01).

AC verificados:
  AC-2: GraphRepository existe con PostgresGraphRepository activo y
        Neo4jGraphRepository stub.
  AC-3: get_graph_repository() respeta GRAPHRAG_BACKEND sin tocar API.
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
# AC-2 — Neo4jGraphRepository stub (hereda GraphRepository)
# ---------------------------------------------------------------------------

def test_neo4j_repo_is_graph_repository() -> None:
    repo = Neo4jGraphRepository()
    assert isinstance(repo, GraphRepository)


async def test_neo4j_repo_get_product_neighbors_raises() -> None:
    repo = Neo4jGraphRepository()
    with pytest.raises(NotImplementedError):
        await repo.get_product_neighbors("SKU-001")


async def test_neo4j_repo_get_competitor_context_raises() -> None:
    repo = Neo4jGraphRepository()
    with pytest.raises(NotImplementedError):
        await repo.get_competitor_context(uuid4())


async def test_neo4j_repo_health_check_reports_stub() -> None:
    repo = Neo4jGraphRepository()
    result = await repo.health_check()
    # El stub no está activo — health_check devuelve estado pero no lanza error
    assert result["backend"] == "neo4j_graph_repository"
    assert result["healthy"] is False


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
