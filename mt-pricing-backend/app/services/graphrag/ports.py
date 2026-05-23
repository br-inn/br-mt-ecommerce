"""GraphStorePort — interfaz hexagonal para cualquier graph store.

Diseño (ADR-016 — connectors hexagonales):

- ``GraphNode`` y ``GraphEdge`` son DTOs Pydantic-like (dataclasses frozen)
  que representan nodos/edges sin acoplar a una implementación concreta.
- ``GraphStorePort`` es un ``Protocol`` (PEP 544) → cualquier objeto con
  estos métodos es válido. No requiere herencia.
- Las operaciones son **idempotentes** por contrato:
    * ``merge_node`` upsert (clave: ``label`` + ``primary_key``).
    * ``merge_edge`` upsert por ``(src, type, dst)``.
    * ``delete_subgraph`` borra el nodo y todos los edges incidentes.

Compatibilidad Cypher:

- ``merge_node`` ↔ ``MERGE (n:Label {pk: $pk}) SET n += $props``.
- ``merge_edge`` ↔ ``MATCH (a {pk:$src}), (b {pk:$dst}) MERGE (a)-[r:TYPE]->(b) SET r += $props``.
- ``query_neighbors`` ↔ ``MATCH (a {pk:$src})-[r]->(b) RETURN r,b``.
- ``delete_subgraph`` ↔ ``MATCH (n {pk:$pk}) DETACH DELETE n``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class GraphNode:
    """Representación inmutable de un nodo del grafo.

    - ``label``: tipo del nodo (``Product``, ``Supplier``, ``MatchCandidate``...).
    - ``primary_key``: identificador único dentro del label (sku/code/uuid).
    - ``properties``: pares clave/valor — sólo tipos JSON-serializables.
    """

    label: str
    primary_key: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphEdge:
    """Representación inmutable de una arista dirigida.

    Identidad: ``(src_label, src_pk, type, dst_label, dst_pk)``.

    Convenciones:
    - ``type`` en SCREAMING_SNAKE_CASE (Cypher idiom): ``SUPPLIED_BY``,
      ``HAS_COST``, ``HAS_MATCH``, ``MADE_OF``.
    - ``properties`` opcional (peso, fecha, score).
    """

    src_label: str
    src_pk: str
    type: str
    dst_label: str
    dst_pk: str
    properties: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class GraphStorePort(Protocol):
    """Operaciones mínimas que debe implementar cualquier backend de grafo."""

    def merge_node(self, node: GraphNode) -> None:
        """Upsert de un nodo. Idempotente por (label, primary_key)."""
        ...

    def merge_edge(self, edge: GraphEdge) -> None:
        """Upsert de una arista dirigida. Idempotente por (src, type, dst)."""
        ...

    def query_neighbors(
        self,
        label: str,
        primary_key: str,
        *,
        edge_type: str | None = None,
    ) -> list[tuple[GraphEdge, GraphNode]]:
        """Devuelve `[(edge, neighbor_node), ...]` — vecinos salientes de un nodo.

        Si ``edge_type`` se pasa, filtra solo aristas de ese tipo. Si el
        nodo no existe, devuelve lista vacía (no lanza excepción).
        """
        ...

    def delete_subgraph(self, label: str, primary_key: str) -> None:
        """Borra el nodo y todas sus aristas incidentes (in/out)."""
        ...

    def health_check(self) -> dict[str, Any]:
        """Diagnóstico operativo (para `/api/v1/graphrag/health`)."""
        ...


__all__ = ["GraphEdge", "GraphNode", "GraphStorePort"]
