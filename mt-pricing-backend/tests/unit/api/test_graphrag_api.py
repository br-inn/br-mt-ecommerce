"""Unit tests del router `app.api.routes.graphrag`.

Patrón (idéntico a `test_matches_api`):
- FastAPI ad-hoc con el router montado en `/api/v1` (sin tocar app/main.py).
- Overrides en `get_db_session`, `get_current_user`, `require_permissions`
  y `get_graph_store` / `get_cdc_dispatcher`.
- Sin DB real; un `CdcEventsRepository` y `CdcDispatcher` fakes responden
  con counts y rowcounts cableados.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.deps import get_current_user, get_db_session
from app.api.routes.graphrag import (
    get_cdc_dispatcher,
    get_graph_store,
    router as graphrag_router,
)
from app.services.graphrag.adapters.neo4j_stub import Neo4jStubGraphStore

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------
class _FakeRole:
    def __init__(self, perms: list[str]) -> None:
        self.code = "tester"
        self.permissions_snapshot = perms


class _FakeUser:
    def __init__(self, perms: list[str]) -> None:
        self.id: UUID = uuid4()
        self.email = "tester@mt.ae"
        self.is_active = True
        self.role = _FakeRole(perms)


class _FakeDispatcher:
    def __init__(self) -> None:
        self.replay_called_with: dict[str, Any] | None = None
        self.replay_rows = 7

    async def replay(
        self,
        *,
        entity_type: str | None = None,
        only_dead_letter: bool = False,
    ) -> int:
        self.replay_called_with = {
            "entity_type": entity_type,
            "only_dead_letter": only_dead_letter,
        }
        return self.replay_rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _build_app(
    *,
    user: _FakeUser,
    store: Neo4jStubGraphStore,
    dispatcher: _FakeDispatcher,
    cdc_counts: dict[str, int],
) -> FastAPI:
    app = FastAPI()
    app.include_router(graphrag_router, prefix="/api/v1")

    # --- session fake con CdcEventsRepository.count_by_status patched ----
    fake_session = MagicMock()

    async def _override_db():  # pragma: no cover
        yield fake_session

    async def _override_user():
        return user

    app.dependency_overrides[get_db_session] = _override_db
    app.dependency_overrides[get_current_user] = _override_user
    app.dependency_overrides[get_graph_store] = lambda: store
    app.dependency_overrides[get_cdc_dispatcher] = lambda: dispatcher

    # `require_permissions(...)` produce un closure `_check`. Inyectamos
    # el override por identidad de la callable registrada en cada route
    # — mismo truco que test_matches_api.
    for route in graphrag_router.routes:
        dependant = getattr(route, "dependant", None)
        if dependant is None:
            continue
        for dependency in dependant.dependencies:
            call = dependency.call
            if call is not None and getattr(call, "__name__", "") == "_check":

                async def _allow(_call=call):  # noqa: ARG001
                    return user

                app.dependency_overrides[call] = _allow

    # --- patch CdcEventsRepository.count_by_status -----------------------
    import app.api.routes.graphrag as graphrag_route_mod

    class _FakeCdcRepo:
        def __init__(self, _session):  # noqa: ANN001
            pass

        async def count_by_status(self) -> dict[str, int]:
            return cdc_counts

    graphrag_route_mod.CdcEventsRepository = _FakeCdcRepo  # type: ignore[attr-defined,assignment]

    return app


async def _client(app: FastAPI) -> AsyncClient:
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://testserver")


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------
async def test_health_returns_store_diag_and_cdc_counts() -> None:
    user = _FakeUser(perms=[])  # health no requiere perms
    store = Neo4jStubGraphStore()
    from app.services.graphrag.ports import GraphNode

    store.merge_node(GraphNode(label="Product", primary_key="X"))
    dispatcher = _FakeDispatcher()
    cdc_counts = {"pending": 5, "processed": 12}
    app = _build_app(user=user, store=store, dispatcher=dispatcher, cdc_counts=cdc_counts)
    async with await _client(app) as ac:
        resp = await ac.get("/api/v1/graphrag/health")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["backend"] == "neo4j_stub_in_memory"
    assert body["healthy"] is True
    assert body["nodes"] == 1
    assert body["edges"] == 0
    assert body["cdc_events"] == cdc_counts


async def test_replay_calls_dispatcher_and_returns_summary() -> None:
    user = _FakeUser(perms=["graphrag:admin"])
    store = Neo4jStubGraphStore()
    dispatcher = _FakeDispatcher()
    app = _build_app(user=user, store=store, dispatcher=dispatcher, cdc_counts={})
    async with await _client(app) as ac:
        resp = await ac.post(
            "/api/v1/graphrag/replay",
            json={"entity_type": "product", "only_dead_letter": True},
        )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["rows_reset"] == 7
    assert body["scope"] == "dead_letter_only"
    assert body["entity_type"] == "product"
    assert dispatcher.replay_called_with == {
        "entity_type": "product",
        "only_dead_letter": True,
    }


async def test_replay_without_body_uses_defaults() -> None:
    user = _FakeUser(perms=["graphrag:admin"])
    store = Neo4jStubGraphStore()
    dispatcher = _FakeDispatcher()
    app = _build_app(user=user, store=store, dispatcher=dispatcher, cdc_counts={})
    async with await _client(app) as ac:
        resp = await ac.post("/api/v1/graphrag/replay")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scope"] == "all"
    assert body["entity_type"] is None
    assert dispatcher.replay_called_with == {
        "entity_type": None,
        "only_dead_letter": False,
    }
