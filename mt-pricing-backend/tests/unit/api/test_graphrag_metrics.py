"""Tests para GET /graphrag/metrics (US-F15-01-06)."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.routes.graphrag import router as graphrag_router
from app.schemas.graphrag import KgMetricsResponse

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# App de test
# ---------------------------------------------------------------------------
def _build_app() -> FastAPI:
    app = FastAPI()
    app.include_router(graphrag_router, prefix="/api/v1")
    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
def test_kg_metrics_response_stub_defaults() -> None:
    """KgMetricsResponse instanciable con valores stub y healthy=True por defecto."""
    r = KgMetricsResponse(
        node_count=0,
        edge_count=0,
        orphan_nodes=0,
        cdc_lag_seconds=0.0,
        backend="stub",
    )
    assert r.node_count == 0
    assert r.edge_count == 0
    assert r.orphan_nodes == 0
    assert r.cdc_lag_seconds == 0.0
    assert r.backend == "stub"
    assert r.healthy is True
    assert r.last_sync is None


def test_kg_metrics_response_neo4j_values() -> None:
    """KgMetricsResponse acepta valores no-zero y marca healthy=True."""
    r = KgMetricsResponse(
        node_count=42,
        edge_count=100,
        orphan_nodes=2,
        cdc_lag_seconds=15.3,
        last_sync="2026-05-12T02:00:00Z",
        backend="neo4j",
        healthy=True,
    )
    assert r.node_count == 42
    assert r.edge_count == 100
    assert r.orphan_nodes == 2
    assert r.cdc_lag_seconds == 15.3


@pytest.mark.asyncio
async def test_metrics_endpoint_stub_mode_returns_200() -> None:
    """GET /graphrag/metrics con GRAPHRAG_BACKEND=stub → 200 + zeros."""
    app = _build_app()

    mock_settings = MagicMock()
    mock_settings.GRAPHRAG_BACKEND = "stub"

    with patch("app.core.config.settings", mock_settings):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/graphrag/metrics")

    assert response.status_code == 200
    data = response.json()
    assert data["backend"] == "stub"
    assert data["node_count"] == 0
    assert data["edge_count"] == 0
    assert data["orphan_nodes"] == 0
    assert data["cdc_lag_seconds"] == 0.0
    assert data["healthy"] is True


@pytest.mark.asyncio
async def test_metrics_endpoint_imports_settings_internally() -> None:
    """Endpoint importa settings dentro del handler → configurable via patch."""
    app = _build_app()

    # Simular backend distinto de neo4j — siempre stub
    mock_settings = MagicMock()
    mock_settings.GRAPHRAG_BACKEND = "memory"

    with patch("app.core.config.settings", mock_settings):
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as client:
            response = await client.get("/api/v1/graphrag/metrics")

    assert response.status_code == 200
    assert response.json()["backend"] == "stub"
