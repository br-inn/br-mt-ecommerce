"""Graph store adapters — implementaciones concretas de `GraphStorePort`.

Fase 1 (S4): `Neo4jStubGraphStore` (in-memory) — default.
Sprint 6: `Neo4jGraphStore` (driver real) — opt-in via
``GRAPHRAG_BACKEND=neo4j`` (ver :mod:`factory`).
"""

from app.services.graphrag.adapters.factory import (
    get_default_graph_store,
    set_default_graph_store,
    shutdown,
)
from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore

__all__ = [
    "Neo4jStubGraphStore",
    "get_default_graph_store",
    "set_default_graph_store",
    "shutdown",
]
