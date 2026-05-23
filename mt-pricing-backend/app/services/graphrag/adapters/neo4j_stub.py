"""Neo4jStubGraphStore — implementación in-memory de `GraphStorePort`.

Diseño:

- Estado en dos diccionarios:
    * ``_nodes: dict[(label, pk), GraphNode]``
    * ``_edges: dict[(src_label, src_pk, type, dst_label, dst_pk), GraphEdge]``
- `merge_node` y `merge_edge` reemplazan/upsertan; `_merge_props` fusiona
  propiedades (no las sustituye en bloque) — emula el patrón Cypher
  ``SET n += $props``.
- Thread-safety: un `threading.RLock` protege las dos estructuras. El stub
  NO está pensado para concurrencia masiva; es soporte para tests + dev.
- NO conecta a Neo4j real — todas las operaciones son síncronas y locales.
- `query_neighbors` itera linealmente sobre `_edges`. O(n) acepta el stub
  porque el dataset es siempre pequeño en pruebas.
"""

from __future__ import annotations

import threading
from collections.abc import Mapping
from typing import Any

from app.services.graphrag.ports import GraphEdge, GraphNode


class Neo4jStubGraphStore:
    """In-memory dict-based graph store que emula la API mínima de Cypher.

    Implementa el ``GraphStorePort`` (duck-typing). NO depende de
    `neo4j-driver` — útil para Fase 1 y para tests unit en CI sin Neo4j.
    """

    def __init__(self) -> None:
        # (label, pk) → GraphNode
        self._nodes: dict[tuple[str, str], GraphNode] = {}
        # (src_label, src_pk, type, dst_label, dst_pk) → GraphEdge
        self._edges: dict[tuple[str, str, str, str, str], GraphEdge] = {}
        self._lock = threading.RLock()

    # ------------------------------------------------------------------ utils
    @staticmethod
    def _merge_props(existing: Mapping[str, Any], incoming: Mapping[str, Any]) -> dict[str, Any]:
        """Equivalente a Cypher ``SET n += $props`` — incoming pisa existing."""
        merged: dict[str, Any] = dict(existing)
        merged.update(incoming)
        return merged

    # ------------------------------------------------------------------ port
    def merge_node(self, node: GraphNode) -> None:
        key = (node.label, node.primary_key)
        with self._lock:
            existing = self._nodes.get(key)
            if existing is None:
                self._nodes[key] = node
            else:
                self._nodes[key] = GraphNode(
                    label=node.label,
                    primary_key=node.primary_key,
                    properties=self._merge_props(existing.properties, node.properties),
                )

    def merge_edge(self, edge: GraphEdge) -> None:
        # Auto-creamos los endpoints si no existen — emula el patrón
        # `MERGE (a:Label {pk:$pk}) MERGE (b:Label {pk:$pk}) MERGE (a)-[r]->(b)`.
        with self._lock:
            self.merge_node(GraphNode(label=edge.src_label, primary_key=edge.src_pk))
            self.merge_node(GraphNode(label=edge.dst_label, primary_key=edge.dst_pk))
            ekey = (
                edge.src_label,
                edge.src_pk,
                edge.type,
                edge.dst_label,
                edge.dst_pk,
            )
            existing = self._edges.get(ekey)
            if existing is None:
                self._edges[ekey] = edge
            else:
                self._edges[ekey] = GraphEdge(
                    src_label=edge.src_label,
                    src_pk=edge.src_pk,
                    type=edge.type,
                    dst_label=edge.dst_label,
                    dst_pk=edge.dst_pk,
                    properties=self._merge_props(existing.properties, edge.properties),
                )

    def query_neighbors(
        self,
        label: str,
        primary_key: str,
        *,
        edge_type: str | None = None,
    ) -> list[tuple[GraphEdge, GraphNode]]:
        out: list[tuple[GraphEdge, GraphNode]] = []
        with self._lock:
            for ekey, edge in self._edges.items():
                src_label, src_pk, etype, dst_label, dst_pk = ekey
                if src_label != label or src_pk != primary_key:
                    continue
                if edge_type is not None and etype != edge_type:
                    continue
                neighbor = self._nodes.get((dst_label, dst_pk))
                if neighbor is None:
                    # Edge huérfana — devolvemos un nodo placeholder para
                    # robustez (no debería ocurrir si solo se usan los
                    # métodos públicos).
                    neighbor = GraphNode(label=dst_label, primary_key=dst_pk)
                out.append((edge, neighbor))
        return out

    def delete_subgraph(self, label: str, primary_key: str) -> None:
        with self._lock:
            self._nodes.pop((label, primary_key), None)
            doomed = [
                k
                for k in self._edges
                if (k[0] == label and k[1] == primary_key)
                or (k[3] == label and k[4] == primary_key)
            ]
            for k in doomed:
                self._edges.pop(k, None)

    def health_check(self) -> dict[str, Any]:
        with self._lock:
            return {
                "backend": "neo4j_stub_in_memory",
                "nodes": len(self._nodes),
                "edges": len(self._edges),
                "healthy": True,
            }

    # ------------------------------------------------------------------ test helpers
    def _reset(self) -> None:
        """Solo para tests — vacía el grafo."""
        with self._lock:
            self._nodes.clear()
            self._edges.clear()

    @property
    def node_count(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        return len(self._edges)


# ---------------------------------------------------------------------------
# Singleton process-wide.
# Razón: el stub vive en memoria; reusamos la misma instancia para que el
# endpoint `/graphrag/health` y la task Celery vean el mismo estado durante
# la vida del proceso. En tests, los fixtures inyectan instancias frescas.
# ---------------------------------------------------------------------------
_default_store: Neo4jStubGraphStore | None = None


def get_default_graph_store() -> Neo4jStubGraphStore:
    global _default_store
    if _default_store is None:
        _default_store = Neo4jStubGraphStore()
    return _default_store


def set_default_graph_store(store: Neo4jStubGraphStore | None) -> None:
    """Permite a los tests inyectar/reset el singleton."""
    global _default_store
    _default_store = store


__all__ = [
    "Neo4jStubGraphStore",
    "get_default_graph_store",
    "set_default_graph_store",
]
