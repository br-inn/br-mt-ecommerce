"""Unit tests del CdcDispatcher — sin DB real, con session fake.

Estrategia:
- ``CdcEvent`` se instancia directamente como objeto Python (no se persiste).
- ``AsyncSession`` se mockea: el dispatcher solo llama a `flush()` y
  `execute(...)` para `fetch_pending`/`replay`. Sustituimos `fetch_pending`
  por un override que devuelve la lista in-memory.
- El graph store es el stub real (`Neo4jStubGraphStore`), así verificamos
  el flujo completo schema_mapper → store.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.db.models.cdc_event import CdcEvent
from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore
from app.services.graphrag.cdc_dispatcher import (
    MAX_ATTEMPTS_BEFORE_DEAD_LETTER,
    CdcDispatcher,
)

pytestmark = pytest.mark.unit


def _make_event(**kw: Any) -> CdcEvent:
    """Construye un CdcEvent transient (sin DB)."""
    return CdcEvent(
        id=kw.get("id", 1),
        entity_type=kw["entity_type"],
        entity_id=kw["entity_id"],
        action=kw["action"],
        payload_jsonb=kw.get("payload", {}),
        status=kw.get("status", "pending"),
        attempts=kw.get("attempts", 0),
    )


def _make_dispatcher_with_events(
    events: list[CdcEvent],
) -> tuple[CdcDispatcher, Neo4jStubGraphStore, MagicMock]:
    session = MagicMock()
    session.flush = AsyncMock(return_value=None)
    session.execute = AsyncMock()
    store = Neo4jStubGraphStore()
    dispatcher = CdcDispatcher(session, store)

    async def _fetch(batch_size: int = 100) -> list[CdcEvent]:
        return events[:batch_size]

    dispatcher.fetch_pending = _fetch  # type: ignore[assignment]
    return dispatcher, store, session


async def test_process_one_product_insert_creates_nodes_and_edges() -> None:
    event = _make_event(
        entity_type="product",
        entity_id="MT-V-038",
        action="insert",
        payload={
            "sku": "MT-V-038",
            "name_en": "Ball Valve",
            "family": "ball_valve",
            "material": "brass",
            "brand": "Pegler",
        },
    )
    dispatcher, store, _ = _make_dispatcher_with_events([event])
    outcome = await dispatcher.process_one(event)
    assert outcome["outcome"] == "processed"
    assert event.status == "processed"
    assert event.processed_at is not None
    # 1 Product + 3 endpoints (Material, Manufacturer, Family) = 4 nodos.
    assert store.node_count == 4
    assert store.edge_count == 3


async def test_process_one_delete_calls_delete_subgraph() -> None:
    # Pre-poblamos el store.
    event_insert = _make_event(
        entity_type="product",
        entity_id="MT-V-001",
        action="insert",
        payload={"sku": "MT-V-001", "family": "valve"},
    )
    dispatcher, store, _ = _make_dispatcher_with_events([event_insert])
    await dispatcher.process_one(event_insert)
    assert store.node_count >= 1

    event_delete = _make_event(
        id=2,
        entity_type="product",
        entity_id="MT-V-001",
        action="delete",
        payload={"sku": "MT-V-001"},
    )
    await dispatcher.process_one(event_delete)
    # El nodo Product debe haber desaparecido (Family auto-creada queda).
    assert all(
        not (n.label == "Product" and n.primary_key == "MT-V-001") for n in store._nodes.values()
    )


async def test_process_one_unsupported_entity_is_noop_processed() -> None:
    event = _make_event(
        entity_type="unknown_kind",
        entity_id="X",
        action="insert",
        payload={"foo": "bar"},
    )
    dispatcher, store, _ = _make_dispatcher_with_events([event])
    outcome = await dispatcher.process_one(event)
    assert outcome["outcome"] == "processed"
    assert store.node_count == 0


async def test_process_one_failure_increments_attempts() -> None:
    event = _make_event(
        entity_type="product",
        entity_id="MT-V-099",
        action="insert",
        payload={"sku": "MT-V-099"},
    )
    dispatcher, store, _ = _make_dispatcher_with_events([event])

    def _boom(node):
        raise RuntimeError("graph down")

    store.merge_node = _boom  # type: ignore[method-assign]

    outcome = await dispatcher.process_one(event)
    assert outcome["outcome"] == "failed"
    assert event.attempts == 1
    assert "graph down" in (event.last_error or "")
    # Segundo intento.
    await dispatcher.process_one(event)
    assert event.attempts == 2
    # Tercer intento → dead_letter.
    final = await dispatcher.process_one(event)
    assert event.attempts == MAX_ATTEMPTS_BEFORE_DEAD_LETTER
    assert event.status == "dead_letter"
    assert final["outcome"] == "dead_letter"


async def test_process_batch_aggregates_outcomes_and_flushes() -> None:
    events = [
        _make_event(
            id=i,
            entity_type="product",
            entity_id=f"S{i}",
            action="insert",
            payload={"sku": f"S{i}", "family": "x"},
        )
        for i in (1, 2, 3)
    ]
    dispatcher, store, session = _make_dispatcher_with_events(events)
    summary = await dispatcher.process_batch(batch_size=10)
    assert summary["scanned"] == 3
    assert summary["processed"] == 3
    assert summary["failed"] == 0
    assert summary["dead_lettered"] == 0
    session.flush.assert_awaited()
    # 3 Product + 1 Family ('x') compartido.
    assert store.node_count == 4
