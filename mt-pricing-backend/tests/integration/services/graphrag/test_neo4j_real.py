"""Integration tests — Neo4jGraphStore contra un Neo4j real (testcontainers).

Cobre el contrato de :class:`GraphStorePort` end-to-end:
- merge_node + merge_edge upsert idempotente
- query_neighbors (con y sin filtro de tipo)
- delete_subgraph borra nodo + aristas incidentes
- health_check reporta `healthy=True` y conteos

Marcador ``@pytest.mark.integration`` — sólo corre cuando se ejecuta el
suite integration (CI dedicado o local con Docker).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from app.services.graphrag.ports import GraphEdge, GraphNode

if TYPE_CHECKING:
    from neo4j import Driver

    from app.services.graphrag.adapters.neo4j_real import Neo4jGraphStore


pytestmark = pytest.mark.integration


# =============================================================================
# Fixtures
# =============================================================================
@pytest.fixture
def neo4j_driver(neo4j_container: str) -> "Driver":
    """Driver fresco apuntando al testcontainer (o instancia externa)."""
    import os

    from neo4j import GraphDatabase

    user = os.environ.get("NEO4J_USER", "neo4j")
    password = os.environ.get("NEO4J_PASSWORD", "devpassword")
    driver = GraphDatabase.driver(neo4j_container, auth=(user, password))
    yield driver
    driver.close()


@pytest.fixture
def store(neo4j_driver: "Driver") -> "Neo4jGraphStore":
    """Adapter sobre el driver del fixture; limpia toda la DB al inicio."""
    from app.services.graphrag.adapters.neo4j_real import Neo4jGraphStore

    s = Neo4jGraphStore(neo4j_driver, database="neo4j")
    # Reset DB para aislamiento — borra nodos y aristas, no constraints.
    with neo4j_driver.session(database="neo4j") as sess:
        sess.run("MATCH (n) DETACH DELETE n").consume()
    return s


# =============================================================================
# Health
# =============================================================================
def test_health_check_reports_healthy(store: "Neo4jGraphStore") -> None:
    diag = store.health_check()
    assert diag["healthy"] is True
    assert diag["backend"] == "neo4j_real"
    assert diag["database"] == "neo4j"
    assert diag["nodes"] == 0
    assert diag["edges"] == 0


# =============================================================================
# merge_node
# =============================================================================
def test_merge_node_creates_with_props(store: "Neo4jGraphStore") -> None:
    store.merge_node(
        GraphNode(
            label="Product",
            primary_key="SKU-001",
            properties={"name_en": "Ball Valve DN50", "active": True},
        )
    )
    diag = store.health_check()
    assert diag["nodes"] == 1


def test_merge_node_is_idempotent_and_merges_props(
    store: "Neo4jGraphStore",
) -> None:
    """Second merge upserts props, no second node."""
    store.merge_node(
        GraphNode(label="Product", primary_key="SKU-002", properties={"a": 1})
    )
    store.merge_node(
        GraphNode(label="Product", primary_key="SKU-002", properties={"b": 2})
    )
    diag = store.health_check()
    assert diag["nodes"] == 1


def test_merge_node_invalid_label_raises(store: "Neo4jGraphStore") -> None:
    with pytest.raises(ValueError, match="Invalid Cypher label"):
        store.merge_node(GraphNode(label="bad-label!", primary_key="x"))


# =============================================================================
# merge_edge + query_neighbors
# =============================================================================
def test_merge_edge_auto_creates_endpoints(store: "Neo4jGraphStore") -> None:
    """merge_edge debe crear nodos endpoints si no existen — idiom MERGE Cypher."""
    store.merge_edge(
        GraphEdge(
            src_label="Product",
            src_pk="SKU-100",
            type="BRANDED",
            dst_label="Manufacturer",
            dst_pk="ACME",
        )
    )
    diag = store.health_check()
    assert diag["nodes"] == 2
    assert diag["edges"] == 1


def test_merge_edge_idempotent_same_triple(store: "Neo4jGraphStore") -> None:
    edge = GraphEdge(
        src_label="Product",
        src_pk="SKU-IDEM",
        type="HAS_COST",
        dst_label="Cost",
        dst_pk="COST-1",
    )
    store.merge_edge(edge)
    store.merge_edge(edge)
    store.merge_edge(edge)
    diag = store.health_check()
    assert diag["edges"] == 1


def test_query_neighbors_returns_outgoing(store: "Neo4jGraphStore") -> None:
    store.merge_node(
        GraphNode(
            label="Product",
            primary_key="SKU-Q1",
            properties={"name_en": "Test"},
        )
    )
    store.merge_edge(
        GraphEdge(
            src_label="Product",
            src_pk="SKU-Q1",
            type="BRANDED",
            dst_label="Manufacturer",
            dst_pk="ACME",
            properties={"since": 2026},
        )
    )
    store.merge_edge(
        GraphEdge(
            src_label="Product",
            src_pk="SKU-Q1",
            type="MADE_OF",
            dst_label="Material",
            dst_pk="ss316",
        )
    )

    neighbors = store.query_neighbors("Product", "SKU-Q1")
    assert len(neighbors) == 2
    by_type = {edge.type: (edge, node) for edge, node in neighbors}
    assert by_type["BRANDED"][1].primary_key == "ACME"
    assert by_type["BRANDED"][1].label == "Manufacturer"
    assert by_type["BRANDED"][0].properties["since"] == 2026
    assert by_type["MADE_OF"][1].primary_key == "ss316"


def test_query_neighbors_filters_by_edge_type(store: "Neo4jGraphStore") -> None:
    store.merge_edge(
        GraphEdge(
            src_label="Product",
            src_pk="SKU-Q2",
            type="BRANDED",
            dst_label="Manufacturer",
            dst_pk="ACME",
        )
    )
    store.merge_edge(
        GraphEdge(
            src_label="Product",
            src_pk="SKU-Q2",
            type="MADE_OF",
            dst_label="Material",
            dst_pk="brass",
        )
    )
    only_branded = store.query_neighbors(
        "Product", "SKU-Q2", edge_type="BRANDED"
    )
    assert len(only_branded) == 1
    assert only_branded[0][0].type == "BRANDED"


def test_query_neighbors_unknown_node_returns_empty(
    store: "Neo4jGraphStore",
) -> None:
    assert store.query_neighbors("Product", "DOES-NOT-EXIST") == []


# =============================================================================
# delete_subgraph
# =============================================================================
def test_delete_subgraph_removes_node_and_incident_edges(
    store: "Neo4jGraphStore",
) -> None:
    store.merge_edge(
        GraphEdge(
            src_label="Product",
            src_pk="SKU-DEL",
            type="BRANDED",
            dst_label="Manufacturer",
            dst_pk="ZBRAND",
        )
    )
    diag_before = store.health_check()
    assert diag_before["nodes"] == 2
    assert diag_before["edges"] == 1

    store.delete_subgraph("Product", "SKU-DEL")

    diag_after = store.health_check()
    # Producto borrado + arista borrada; Manufacturer sigue (no in DETACH scope).
    assert diag_after["nodes"] == 1
    assert diag_after["edges"] == 0


# =============================================================================
# Constraint enforcement (uniqueness por primary_key dentro del label)
# =============================================================================
def test_uniqueness_constraint_enforced(
    store: "Neo4jGraphStore", neo4j_driver: "Driver"
) -> None:
    """Constraint uniqueness por (Label, primary_key) creada lazy — un INSERT
    duplicado vía Cypher CREATE (sin MERGE) debería fallar.
    """
    from neo4j.exceptions import ConstraintError

    # Trigger constraint creation for Product.
    store.merge_node(GraphNode(label="Product", primary_key="UNI-1"))

    with neo4j_driver.session(database="neo4j") as sess:
        with pytest.raises(ConstraintError):
            sess.run(
                "CREATE (n:Product {primary_key: $pk})", pk="UNI-1"
            ).consume()
