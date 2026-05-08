"""GraphRAG API — health + replay (US-RND-01-11, Sprint 4).

Endpoints:

- ``GET  /api/v1/graphrag/health``  — dump del estado del graph store + CDC.
- ``POST /api/v1/graphrag/replay``  — admin: resetea rows a `pending` para
  reprocesado. Requiere permiso ``graphrag:admin`` (seed en migración 025).

Diseño:
- Router montable independiente (no se incluye automáticamente en
  ``app/api/routes/__init__.py`` — patch documentado en el reporte).
- Inyección del graph store via dependency `get_graph_store` para que los
  tests puedan sustituir el singleton in-memory por una instancia limpia.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.repositories.cdc_events import CdcEventsRepository
from app.schemas.graphrag import (
    GraphRagHealthResponse,
    GraphRagReplayRequest,
    GraphRagReplayResponse,
)
from app.services.graphrag.adapters import get_default_graph_store
from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore
from app.services.graphrag.cdc_dispatcher import CdcDispatcher
from app.services.graphrag.ports import GraphStorePort

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
    summary="Health del scaffold GraphRAG (graph store + CDC outbox)",
    description=(
        "Devuelve diagnóstico del scaffold GraphRAG: backend del graph "
        "store (Neo4jStub/in-memory Sprint 4), nodes/edges count y "
        "estados del CDC outbox."
    ),
    operation_id="graphragGetHealth",
)
async def health(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    graph: Annotated[GraphStorePort, Depends(get_graph_store)],
) -> GraphRagHealthResponse:
    diag = graph.health_check()
    repo = CdcEventsRepository(session)
    counts = await repo.count_by_status()
    return GraphRagHealthResponse(
        backend=str(diag.get("backend", "unknown")),
        healthy=bool(diag.get("healthy", False)),
        nodes=int(diag.get("nodes", 0)),
        edges=int(diag.get("edges", 0)),
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


# Re-export para el test fixture
__all__ = [
    "router",
    "get_graph_store",
    "get_cdc_dispatcher",
    "Neo4jStubGraphStore",
]
