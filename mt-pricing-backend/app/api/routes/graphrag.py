"""GraphRAG API — health + replay + metrics (US-RND-01-11, US-F15-01-06).

Endpoints:

- ``GET  /api/v1/graphrag/health``   — dump del estado del graph store + CDC.
- ``POST /api/v1/graphrag/replay``   — admin: resetea rows a `pending` para
  reprocesado. Requiere permiso ``graphrag:admin`` (seed en migración 025).
- ``GET  /api/v1/graphrag/metrics``  — métricas KG (nodos, edges, orphans,
  cdc_lag). HTTP 503 si lag > 300 s. Stub mode retorna zeros.

Diseño:
- Router montable independiente (no se incluye automáticamente en
  ``app/api/routes/__init__.py`` — patch documentado en el reporte).
- Inyección del graph store via dependency `get_graph_store` para que los
  tests puedan sustituir el singleton in-memory por una instancia limpia.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.cdc_events import CdcEventsRepository
from app.schemas.graphrag import (
    GraphRagHealthResponse,
    GraphRagReplayRequest,
    GraphRagReplayResponse,
    KgMetricsResponse,
)
from app.services.comparator.graph_repository import get_graph_repository
from app.services.graphrag.adapters import get_default_graph_store
from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore
from app.services.graphrag.cdc_dispatcher import CdcDispatcher
from app.services.graphrag.ports import GraphStorePort

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/graphrag", tags=["graphrag"])


# ---------------------------------------------------------------------------
# DI
# ---------------------------------------------------------------------------
def get_graph_store() -> GraphStorePort:
    """Devuelve la instancia singleton activa (stub o Neo4j real según
    ``settings.GRAPHRAG_BACKEND``).

    Tests overridean esta dependency con una instancia fresca via
    ``app.dependency_overrides``.
    """
    return get_default_graph_store()


def get_cdc_dispatcher(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    graph: Annotated[GraphStorePort, Depends(get_graph_store)],
) -> CdcDispatcher:
    return CdcDispatcher(session, graph)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.get(
    "/health",
    response_model=GraphRagHealthResponse,
    summary="Health del scaffold GraphRAG (graph repository + CDC outbox)",
    description=(
        "Devuelve diagnóstico del scaffold GraphRAG: backend del graph "
        "repository (Neo4jGraphRepository o PostgresGraphRepository según "
        "GRAPHRAG_BACKEND), nodes/edges count y estados del CDC outbox. "
        "HTTP 200 cuando healthy=True; HTTP 503 cuando healthy=False."
    ),
    operation_id="graphragGetHealth",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Graph backend unhealthy"},
    },
)
async def health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    response: Response,
) -> GraphRagHealthResponse:
    graph_repo = get_graph_repository()
    diag = await graph_repo.health_check()
    # Para Neo4jGraphRepository, nodes/edges están en store_health anidado.
    store_diag = diag.get("store_health", diag)
    is_healthy = bool(diag.get("healthy", False))
    repo = CdcEventsRepository(session)
    counts = await repo.count_by_status()
    if not is_healthy:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    return GraphRagHealthResponse(
        backend=str(diag.get("backend", "unknown")),
        healthy=is_healthy,
        nodes=int(store_diag.get("nodes", 0)),
        edges=int(store_diag.get("edges", 0)),
        cdc_events=counts,
    )


@router.post(
    "/replay",
    response_model=GraphRagReplayResponse,
    status_code=status.HTTP_200_OK,
    summary="Resetea rows cdc_events a `pending` (admin only — graphrag:admin)",
    description=(
        "Resetea filas en `cdc_events` a status `pending` para forzar "
        "re-procesamiento. Soporta filtrado por entity_type y modo "
        "`only_dead_letter`. Admin only."
    ),
    operation_id="graphragReplayCdc",
)
async def replay(
    payload: GraphRagReplayRequest | None = None,
    _user: User = Depends(require_permissions("graphrag:admin")),
    dispatcher: CdcDispatcher = Depends(get_cdc_dispatcher),
) -> GraphRagReplayResponse:
    body = payload or GraphRagReplayRequest()
    rows = await dispatcher.replay(
        entity_type=body.entity_type,
        only_dead_letter=body.only_dead_letter,
    )
    return GraphRagReplayResponse(
        rows_reset=rows,
        scope="dead_letter_only" if body.only_dead_letter else "all",
        entity_type=body.entity_type,
    )


@router.get(
    "/metrics",
    response_model=KgMetricsResponse,
    summary="Métricas del Knowledge Graph (US-F15-01-06)",
    description=(
        "Devuelve métricas del KG: node_count, edge_count, orphan_nodes, "
        "cdc_lag_seconds. Retorna HTTP 503 si cdc_lag > 300 s. "
        "En modo stub (GRAPHRAG_BACKEND != neo4j) retorna zeros y healthy=True."
    ),
    operation_id="graphragGetMetrics",
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "description": "Lag CDC demasiado alto o backend no disponible"
        },
    },
)
async def get_kg_metrics() -> KgMetricsResponse:
    """Métricas del Knowledge Graph. HTTP 503 si lag > 300s."""
    from app.core.config import settings

    backend = settings.GRAPHRAG_BACKEND

    if backend != "neo4j":
        # Stub mode — retorna zeros, siempre healthy
        return KgMetricsResponse(
            node_count=0,
            edge_count=0,
            orphan_nodes=0,
            cdc_lag_seconds=0.0,
            backend="stub",
        )

    try:
        graph = get_default_graph_store()
        metrics = await asyncio.to_thread(_compute_kg_metrics, graph)

        if metrics["cdc_lag_seconds"] > 300:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "error": "cdc_lag_too_high",
                    "cdc_lag_seconds": metrics["cdc_lag_seconds"],
                },
            )

        return KgMetricsResponse(**metrics, backend="neo4j")

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("graphrag.metrics.failed: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "metrics_unavailable"},
        )


def _compute_kg_metrics(graph) -> dict:  # noqa: ANN001
    """Ejecuta queries Neo4j para métricas (sync, llamar via asyncio.to_thread)."""
    driver = getattr(graph, "_driver", None)
    if driver is None:
        return {
            "node_count": 0,
            "edge_count": 0,
            "orphan_nodes": 0,
            "cdc_lag_seconds": 0.0,
            "last_sync": None,
            "healthy": True,
        }

    database = getattr(graph, "_database", "neo4j")
    with driver.session(database=database) as s:
        node_count = s.run("MATCH (n) RETURN count(n) AS cnt").single()["cnt"]
        edge_count = s.run("MATCH ()-[r]->() RETURN count(r) AS cnt").single()["cnt"]
        orphan_nodes = s.run("MATCH (n) WHERE NOT (n)--() RETURN count(n) AS cnt").single()["cnt"]

    return {
        "node_count": node_count,
        "edge_count": edge_count,
        "orphan_nodes": orphan_nodes,
        "cdc_lag_seconds": 0.0,  # TODO: implementar con consulta Postgres en S11
        "last_sync": None,
        "healthy": True,
    }


# Re-export para el test fixture
__all__ = [
    "router",
    "get_graph_store",
    "get_cdc_dispatcher",
    "Neo4jStubGraphStore",
]
