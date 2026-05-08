"""Neo4jGraphStore — adapter real contra Neo4j 5 (driver oficial).

Implementa :class:`GraphStorePort` usando ``neo4j.GraphDatabase.driver``.
Cumple el mismo contrato que :class:`Neo4jStubGraphStore` — los tests del
``CdcDispatcher`` que se aprueban contra el stub deben pasar también
contra esta implementación cuando hay Neo4j real disponible.

Convenciones Cypher:

- ``merge_node`` ↔ ``MERGE (n:Label {primary_key:$pk}) SET n += $props``.
- ``merge_edge`` ↔ ``MATCH (a:SrcLabel {primary_key:$src})``
  ``MATCH (b:DstLabel {primary_key:$dst})``
  ``MERGE (a)-[r:TYPE]->(b) SET r += $props``.
- ``query_neighbors`` ↔ ``MATCH (a:Label {primary_key:$pk})-[r]->(b)``
  ``RETURN type(r) AS type, properties(r) AS props, labels(b) AS labels,``
  ``b.primary_key AS pk, properties(b) AS bprops``.
- ``delete_subgraph`` ↔ ``MATCH (n:Label {primary_key:$pk}) DETACH DELETE n``.

Constraints (uniqueness por (Label, primary_key)) se crean lazy on-demand
la primera vez que se ve un Label nuevo. Esto evita tener que enumerar
todos los labels al arranque y mantiene el contrato del Port.
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING, Any

from app.services.graphrag.ports import GraphEdge, GraphNode

if TYPE_CHECKING:  # pragma: no cover
    from neo4j import Driver, Session

logger = logging.getLogger(__name__)


# Cypher injection guard: validamos que labels y types vengan de un set
# whitelist runtime — Cypher no parametriza labels/types, así que un label
# arbitrario abriría una vía de inyección si la fuente no es trusted.
_LABEL_PATTERN = r"^[A-Za-z_][A-Za-z0-9_]*$"


def _safe_label(label: str) -> str:
    import re

    if not re.match(_LABEL_PATTERN, label):
        raise ValueError(f"Invalid Cypher label/type: {label!r}")
    return label


class Neo4jGraphStore:
    """Adapter Neo4j real — implementa :class:`GraphStorePort`.

    Args:
        driver: instancia de ``neo4j.Driver`` ya configurada (URI + auth).
        database: nombre de la BD (default ``neo4j``).

    Notas:
    - El driver se gestiona externamente (singleton via :mod:`factory`)
      porque su ciclo de vida supera al del adapter (varios servicios lo
      reusan). El adapter NO cierra el driver — eso lo hace el factory
      en shutdown.
    - Métodos síncronos: el driver oficial expone ``Session`` síncrona
      (las tasks Celery son sync; las rutas FastAPI las invocan vía
      ``asyncio.to_thread`` si hace falta — no en este sprint).
    """

    def __init__(
        self,
        driver: "Driver",
        *,
        database: str = "neo4j",
    ) -> None:
        self._driver = driver
        self._database = database
        self._ensured_labels: set[str] = set()
        self._lock = threading.RLock()

    @property
    def database(self) -> str:
        return self._database

    def _session(self) -> "Session":
        return self._driver.session(database=self._database)

    def _ensure_constraint(self, label: str) -> None:
        safe = _safe_label(label)
        with self._lock:
            if safe in self._ensured_labels:
                return
            cypher = (
                f"CREATE CONSTRAINT IF NOT EXISTS "
                f"FOR (n:{safe}) REQUIRE n.primary_key IS UNIQUE"
            )
            try:
                with self._session() as s:
                    s.run(cypher).consume()
                self._ensured_labels.add(safe)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "neo4j_real.ensure_constraint failed label=%s err=%s",
                    safe,
                    exc,
                )

    def merge_node(self, node: GraphNode) -> None:
        label = _safe_label(node.label)
        self._ensure_constraint(label)
        cypher = (
            f"MERGE (n:{label} {{primary_key: $pk}}) "
            f"SET n += $props"
        )
        with self._session() as s:
            s.run(
                cypher,
                pk=node.primary_key,
                props=dict(node.properties),
            ).consume()

    def merge_edge(self, edge: GraphEdge) -> None:
        src_label = _safe_label(edge.src_label)
        dst_label = _safe_label(edge.dst_label)
        edge_type = _safe_label(edge.type)
        self._ensure_constraint(src_label)
        self._ensure_constraint(dst_label)
        # MERGE asegura idempotencia por (src, type, dst).
        cypher = (
            f"MERGE (a:{src_label} {{primary_key: $src_pk}}) "
            f"MERGE (b:{dst_label} {{primary_key: $dst_pk}}) "
            f"MERGE (a)-[r:{edge_type}]->(b) "
            f"SET r += $props"
        )
        with self._session() as s:
            s.run(
                cypher,
                src_pk=edge.src_pk,
                dst_pk=edge.dst_pk,
                props=dict(edge.properties),
            ).consume()

    def query_neighbors(
        self,
        label: str,
        primary_key: str,
        *,
        edge_type: str | None = None,
    ) -> list[tuple[GraphEdge, GraphNode]]:
        safe_label = _safe_label(label)
        if edge_type is not None:
            safe_type = _safe_label(edge_type)
            cypher = (
                f"MATCH (a:{safe_label} {{primary_key: $pk}})"
                f"-[r:{safe_type}]->(b) "
                f"RETURN type(r) AS etype, properties(r) AS eprops, "
                f"       labels(b) AS blabels, b.primary_key AS bpk, "
                f"       properties(b) AS bprops"
            )
        else:
            cypher = (
                f"MATCH (a:{safe_label} {{primary_key: $pk}})-[r]->(b) "
                f"RETURN type(r) AS etype, properties(r) AS eprops, "
                f"       labels(b) AS blabels, b.primary_key AS bpk, "
                f"       properties(b) AS bprops"
            )
        out: list[tuple[GraphEdge, GraphNode]] = []
        with self._session() as s:
            result = s.run(cypher, pk=primary_key)
            for record in result:
                blabels = record["blabels"] or []
                # Tomamos el primer label — Neo4j permite multi-label, pero
                # el SchemaMapper siempre asigna uno solo en este pipeline.
                dst_label = blabels[0] if blabels else "Unknown"
                bpk = record["bpk"] or ""
                bprops = dict(record["bprops"] or {})
                # primary_key vive en props y también como atributo del nodo —
                # quitamos del dict para no duplicarlo.
                bprops.pop("primary_key", None)
                neighbor = GraphNode(
                    label=str(dst_label),
                    primary_key=str(bpk),
                    properties=bprops,
                )
                eprops = dict(record["eprops"] or {})
                edge = GraphEdge(
                    src_label=label,
                    src_pk=primary_key,
                    type=str(record["etype"]),
                    dst_label=str(dst_label),
                    dst_pk=str(bpk),
                    properties=eprops,
                )
                out.append((edge, neighbor))
        return out

    def delete_subgraph(self, label: str, primary_key: str) -> None:
        safe = _safe_label(label)
        cypher = (
            f"MATCH (n:{safe} {{primary_key: $pk}}) DETACH DELETE n"
        )
        with self._session() as s:
            s.run(cypher, pk=primary_key).consume()

    def health_check(self) -> dict[str, Any]:
        try:
            with self._session() as s:
                # `RETURN 1` confirma round-trip Bolt + auth.
                s.run("RETURN 1 AS one").consume()
                # Conteos globales (cap conservador — para grafos grandes
                # esto se reemplaza por un count específico por label).
                rec_n = s.run("MATCH (n) RETURN count(n) AS c").single()
                rec_e = s.run("MATCH ()-[r]->() RETURN count(r) AS c").single()
                nodes = int(rec_n["c"]) if rec_n else 0
                edges = int(rec_e["c"]) if rec_e else 0
                return {
                    "backend": "neo4j_real",
                    "database": self._database,
                    "nodes": nodes,
                    "edges": edges,
                    "healthy": True,
                }
        except Exception as exc:  # noqa: BLE001
            logger.warning("neo4j_real.health_check failed: %s", exc)
            return {
                "backend": "neo4j_real",
                "database": self._database,
                "nodes": 0,
                "edges": 0,
                "healthy": False,
                "error": f"{type(exc).__name__}: {exc}",
            }


__all__ = ["Neo4jGraphStore"]
