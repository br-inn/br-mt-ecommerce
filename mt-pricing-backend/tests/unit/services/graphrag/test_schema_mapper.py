"""Unit tests del SchemaMapper — pure functions, no IO."""

from __future__ import annotations

import pytest

from app.services.graphrag.schema_mapper import (
    EDGE_BELONGS_TO,
    EDGE_BRANDED,
    EDGE_FROM_SUPPLIER,
    EDGE_HAS_COST,
    EDGE_HAS_MATCH,
    EDGE_LISTED_ON,
    EDGE_MADE_OF,
    EDGE_USES_CURRENCY,
    LABEL_COST,
    LABEL_MATCH_CANDIDATE,
    LABEL_PRODUCT,
    LABEL_SUPPLIER,
    SchemaMapper,
)

pytestmark = pytest.mark.unit


def test_map_product_creates_node_and_three_edges() -> None:
    nodes, edges = SchemaMapper.map_event(
        entity_type="product",
        action="insert",
        payload={
            "sku": "MT-V-038",
            "name_en": "Ball Valve DN50",
            "family": "ball_valve",
            "material": "brass_CW617N",
            "brand": "Pegler",
        },
    )
    assert len(nodes) == 1
    assert nodes[0].label == LABEL_PRODUCT
    assert nodes[0].primary_key == "MT-V-038"

    edge_types = {e.type for e in edges}
    assert edge_types == {EDGE_MADE_OF, EDGE_BRANDED, EDGE_BELONGS_TO}


def test_map_product_skips_missing_optional_fields() -> None:
    nodes, edges = SchemaMapper.map_event(
        entity_type="product",
        action="update",
        payload={"sku": "X1", "family": "valve"},
    )
    assert len(nodes) == 1
    assert {e.type for e in edges} == {EDGE_BELONGS_TO}


def test_map_product_without_sku_returns_empty() -> None:
    nodes, edges = SchemaMapper.map_event(
        entity_type="product",
        action="insert",
        payload={"name_en": "no sku"},
    )
    assert nodes == []
    assert edges == []


def test_map_supplier_with_currency() -> None:
    nodes, edges = SchemaMapper.map_event(
        entity_type="supplier",
        action="insert",
        payload={
            "code": "PEGLER",
            "name": "Pegler Yorkshire",
            "contract_currency": "EUR",
        },
    )
    assert nodes[0].label == LABEL_SUPPLIER
    assert {e.type for e in edges} == {EDGE_USES_CURRENCY}


def test_map_cost_links_product_and_supplier() -> None:
    nodes, edges = SchemaMapper.map_event(
        entity_type="cost",
        action="insert",
        payload={
            "id": "cost-uuid-1",
            "sku": "MT-V-038",
            "supplier_code": "PEGLER",
            "scheme_code": "FOB_EU",
            "currency_origin": "EUR",
        },
    )
    assert nodes[0].label == LABEL_COST
    assert {e.type for e in edges} == {EDGE_HAS_COST, EDGE_FROM_SUPPLIER}


def test_map_match_candidate_links_product_and_channel() -> None:
    nodes, edges = SchemaMapper.map_event(
        entity_type="match_candidate",
        action="insert",
        payload={
            "id": "match-uuid",
            "product_sku": "MT-V-038",
            "channel": "amazon_uae",
            "external_id": "B0XYZ",
            "title": "Brass ball valve",
            "score": 87,
            "kind": "peer",
            "status": "pending",
        },
    )
    assert nodes[0].label == LABEL_MATCH_CANDIDATE
    assert {e.type for e in edges} == {EDGE_HAS_MATCH, EDGE_LISTED_ON}


def test_map_event_delete_returns_empty() -> None:
    nodes, edges = SchemaMapper.map_event(
        entity_type="product", action="delete", payload={"sku": "X"}
    )
    assert nodes == []
    assert edges == []


def test_map_event_unsupported_entity_logs_and_returns_empty() -> None:
    nodes, edges = SchemaMapper.map_event(
        entity_type="hypothetical_entity",
        action="insert",
        payload={"foo": "bar"},
    )
    assert nodes == []
    assert edges == []


def test_primary_label_known_and_unknown() -> None:
    assert SchemaMapper.primary_label("product") == LABEL_PRODUCT
    assert SchemaMapper.primary_label("supplier") == LABEL_SUPPLIER
    assert SchemaMapper.primary_label("cost") == LABEL_COST
    assert SchemaMapper.primary_label("match_candidate") == LABEL_MATCH_CANDIDATE
    assert SchemaMapper.primary_label("nope") is None


def test_filter_props_drops_none_and_stringifies_decimal() -> None:
    from decimal import Decimal

    nodes, _ = SchemaMapper.map_event(
        entity_type="cost",
        action="update",
        payload={
            "id": "c1",
            "sku": "S1",
            "scheme_landed_aed": Decimal("100.50"),
            "version": 2,
            "extra_should_be_dropped": "yes",  # no está en la whitelist
        },
    )
    props = nodes[0].properties
    # Decimal serializa a str (via _filter_props).
    assert props["scheme_landed_aed"] == "100.50"
    assert props["version"] == 2
    assert "extra_should_be_dropped" not in props
