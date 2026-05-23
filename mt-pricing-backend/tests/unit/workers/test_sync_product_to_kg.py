"""Unit tests para la Celery task `mt.graphrag.sync_product_to_kg`.

Estrategia:
- Patcheamos `get_default_graph_store` para retornar un MagicMock.
- Corremos `_sync_product` directamente (helper async) para validar
  que llama `merge_node` en upsert y `delete_subgraph` en delete.
- Probamos la task completa con `.apply()` en modo eager (sin broker).
"""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Tests sobre el helper async _sync_product
# ---------------------------------------------------------------------------


def test_sync_product_upsert_calls_merge_node() -> None:
    """_sync_product con operation=upsert llama merge_node en el graph store."""
    mock_graph = MagicMock()

    with patch(
        "app.services.graphrag.adapters.factory.get_default_graph_store",
        return_value=mock_graph,
    ):
        # Reimportar para que el patch tome efecto en el módulo de la task.
        from app.workers.tasks import graphrag as task_mod

        with patch.object(task_mod, "get_default_graph_store", return_value=mock_graph):
            result = asyncio.run(task_mod._sync_product("PROD-001", "upsert"))

    mock_graph.merge_node.assert_called_once()
    assert result["action"] == "upserted"


def test_sync_product_delete_calls_delete_subgraph() -> None:
    """_sync_product con operation=delete llama delete_subgraph."""
    mock_graph = MagicMock()

    from app.workers.tasks import graphrag as task_mod

    with patch.object(task_mod, "get_default_graph_store", return_value=mock_graph):
        result = asyncio.run(task_mod._sync_product("PROD-001", "delete"))

    mock_graph.delete_subgraph.assert_called_once_with("Product", "PROD-001")
    assert result["action"] == "deleted"


def test_sync_product_insert_treated_as_upsert() -> None:
    """operation distinto de 'delete' usa la rama upsert."""
    mock_graph = MagicMock()

    from app.workers.tasks import graphrag as task_mod

    with patch.object(task_mod, "get_default_graph_store", return_value=mock_graph):
        result = asyncio.run(task_mod._sync_product("PROD-002", "insert"))

    mock_graph.merge_node.assert_called_once()
    mock_graph.delete_subgraph.assert_not_called()
    assert result["action"] == "upserted"


# ---------------------------------------------------------------------------
# Tests sobre la Celery task sync_product_to_kg (modo eager)
# ---------------------------------------------------------------------------


def test_sync_product_to_kg_task_returns_metadata() -> None:
    """La task retorna product_id, operation y latency_ms."""
    mock_graph = MagicMock()

    from app.workers.tasks import graphrag as task_mod

    async def _fake_sync(product_id: str, operation: str) -> dict:  # noqa: ARG001
        return {"action": "upserted"}

    with patch.object(task_mod, "_sync_product", _fake_sync):
        result = task_mod.sync_product_to_kg.apply(
            kwargs={"product_id": "PROD-999", "operation": "upsert"}
        ).get()

    assert result["product_id"] == "PROD-999"
    assert result["operation"] == "upsert"
    assert "latency_ms" in result
    assert isinstance(result["latency_ms"], int)


def test_sync_product_to_kg_default_operation_is_upsert() -> None:
    """operation por defecto es 'upsert'."""
    from app.workers.tasks import graphrag as task_mod

    captured: dict = {}

    async def _fake_sync(product_id: str, operation: str) -> dict:
        captured["operation"] = operation
        return {"action": "upserted"}

    with patch.object(task_mod, "_sync_product", _fake_sync):
        task_mod.sync_product_to_kg.apply(kwargs={"product_id": "X"}).get()

    assert captured["operation"] == "upsert"
