"""GraphRAG scaffold (US-RND-01-11, Sprint 4).

Este paquete introduce las abstracciones hexagonales para que el comparador
en Fase 2+ pueda consultar un knowledge graph (Neo4j) sin refactor del
pipeline matching de Fase 1.

Componentes:

- ``ports.GraphStorePort``: interfaz Protocol que define las operaciones
  mínimas sobre cualquier graph store (`merge_node`, `merge_edge`,
  `query_neighbors`, `delete_subgraph`).
- ``adapters.neo4j_stub.Neo4jStubGraphStore``: implementación in-memory
  dict-based que emula `MERGE`/`MATCH`/`DELETE` Cypher. Por defecto la
  aplicación usa este adapter en Fase 1; la swap a un Neo4j real ocurre
  en Fase 2+ con un nuevo adapter (no incluido aquí).
- ``schema_mapper.SchemaMapper``: traduce filas de Postgres
  (Product/Supplier/Cost/MatchCandidate) a operaciones de grafo (nodos +
  edges). Es puro — sin IO.
- ``cdc_dispatcher.CdcDispatcher``: consume rows de la tabla
  ``cdc_events`` (outbox pattern) y emite mutaciones contra el graph
  store usando el ``SchemaMapper``. Idempotente.

NO incluye:

- Conexión a Neo4j real (ADR-041 — Fase 2+).
- UI de exploración del grafo (Fase 3+).
- Indexación vectorial (`embedding`-aware queries) — pendiente ADR-074.
"""

from app.services.graphrag.ports import (
    GraphEdge,
    GraphNode,
    GraphStorePort,
)

__all__ = ["GraphStorePort", "GraphNode", "GraphEdge"]
