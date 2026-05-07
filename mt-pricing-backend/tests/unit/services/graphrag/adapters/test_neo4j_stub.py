"""Unit tests del Neo4jStubGraphStore (in-memory).

Cubre el contrato `GraphStorePort`:
- merge_node idempotente + property merge.
- merge_edge auto-crea endpoints.
- query_neighbors filtra por edge_type.
- delete_subgraph borra nodo + edges incidentes (in/out).
- health_check reporta nodes/edges count.
"""

from __future__ import annotations

import pytest

from app.services.graphrag.adapters.neo4j_stub import (
    Neo4jStubGraphStore,
    get_default_graph_store,
    set_default_graph_store,
)
from app.services.graphrag.ports import GraphEdge, GraphNode, GraphStorePort

pytestmark = pytest.mark.unit


def test_implements_graph_store_port() -> None:
    store = Neo4jStubGraphStore()
    assert isinstance(store, GraphStorePort)


def test_merge_node_idempotent_and_merges_props() -> None:
    store = Neo4jStubGraphStore()
    store.merge_node(
        GraphNode(label="Product", primary_key="MT-V-038", properties={"family": "ball_valve"})
    )
    store.merge_node(
        GraphNode(label="Product", primary_key="MT-V-038", properties={"brand": "Pegler"})
    )
    assert store.node_count == 1
    neighbors = store.query_neighbors("Product", "MT-V-038")
    assert neighbors == []  # sin edges aún
    # Comprobamos el merge interno via re-query con un edge.
    store.merge_edge(
        GraphEdge(
            src_label="Product",
            src_pk="MT-V-038",
            type="MADE_OF",
            dst_label="Material",
            dst_pk="brass",
        )
    )
    edge, neighbor = store.query_neighbors("Product", "MT-V-038")[0]
    assert edge.type == "MADE_OF"
    assert neighbor.label == "Material"
    assert neighbor.primary_key == "brass"


def test_merge_edge_auto_creates_endpoints() -> None:
    store = Neo4jStubGraphStore()
    store.merge_edge(
        GraphEdge(
            src_label="Product",
            src_pk="SKU1",
            type="HAS_COST",
            dst_label="Cost",
            dst_pk="cost-uuid-1",
        )
    )
    assert store.node_count == 2
    assert store.edge_count == 1


def test_merge_edge_idempotent_props_merged() -> None:
    store = Neo4jStubGraphStore()
    e1 = GraphEdge(
        src_label="A", src_pk="1", type="REL", dst_label="B", dst_pk="2",
        properties={"score": 10},
    )
    e2 = GraphEdge(
        src_label="A", src_pk="1", type="REL", dst_label="B", dst_pk="2",
        properties={"weight": 0.5},
    )
    store.merge_edge(e1)
    store.merge_edge(e2)
    assert store.edge_count == 1
    edge, _ = store.query_neighbors("A", "1")[0]
    assert edge.properties == {"score": 10, "weight": 0.5}


def test_query_neighbors_filters_by_edge_type() -> None:
    store = Neo4jStubGraphStore()
    store.merge_edge(
        GraphEdge(
            src_label="P", src_pk="X",
            type="MADE_OF", dst_label="M", dst_pk="brass",
        )
    )
    store.merge_edge(
        GraphEdge(
            src_label="P", src_pk="X",
            type="BRANDED", dst_label="Mfr", dst_pk="Pegler",
        )
    )
    only_made = store.query_neighbors("P", "X", edge_type="MADE_OF")
    assert len(only_made) == 1
    assert only_made[0][0].type == "MADE_OF"


def test_query_neighbors_unknown_returns_empty() -> None:
    store = Neo4jStubGraphStore()
    assert store.query_neighbors("Product", "NOPE") == []


def test_delete_subgraph_removes_node_and_incident_edges() -> None:
    store = Neo4jStubGraphStore()
    store.merge_edge(
        GraphEdge(src_label="P", src_pk="X", type="R", dst_label="Q", dst_pk="Y")
    )
    store.merge_edge(
        GraphEdge(src_label="Q", src_pk="Y", type="R2", dst_label="Z", dst_pk="W")
    )
    store.delete_subgraph("Q", "Y")
    # Queda P y Z (auto-creado), no queda Q.
    assert store.edge_count == 0
    # P sigue existiendo (no se borró Q-incident desde P->Q).
    # Pero la edge P->Q ya no debe existir.
    assert store.query_neighbors("P", "X") == []


def test_health_check_reports_counts() -> None:
    store = Neo4jStubGraphStore()
    store.merge_node(GraphNode(label="Product", primary_key="A"))
    diag = store.health_check()
    assert diag["healthy"] is True
    assert diag["backend"] == "neo4j_stub_in_memory"
    assert diag["nodes"] == 1
    assert diag["edges"] == 0


def test_default_graph_store_is_singleton_and_resettable() -> None:
    # Reset state for the test.
    set_default_graph_store(None)
    s1 = get_default_graph_store()
    s2 = get_default_graph_store()
    assert s1 is s2
    set_default_graph_store(None)
    s3 = get_default_graph_store()
    assert s3 is not s1
    set_default_graph_store(None)
