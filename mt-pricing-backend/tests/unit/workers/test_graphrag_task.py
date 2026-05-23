"""Unit tests para el Celery task `mt.graphrag.process_cdc_batch`.

Estrategia:

- No tocamos DB/Postgres ni Neo4j — patcheamos `_run_dispatch` para retornar
  un resumen sintético, y verificamos que la task:
    * Devuelve el dict sin la clave `outcomes` (filtrado para no inflar logs).
    * Propaga la excepción si `_run_dispatch` falla, tras loguear.
    * Acepta `batch_size` como argumento.

Esto cubre el contrato del task sin depender de eventos persistidos.
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

pytestmark = pytest.mark.unit


def _fake_summary() -> dict:
    return {
        "scanned": 5,
        "processed": 4,
        "failed": 1,
        "dead_lettered": 0,
        "outcomes": [{"event_id": i, "outcome": "processed"} for i in range(4)]
        + [{"event_id": 5, "outcome": "failed", "error": "boom"}],
    }


def test_process_cdc_batch_returns_summary_without_outcomes() -> None:
    from app.workers.tasks import graphrag as task_mod

    summary = _fake_summary()

    async def _fake_run(batch_size: int = 100):
        return summary

    with patch.object(task_mod, "_run_dispatch", _fake_run):
        result = task_mod.process_cdc_batch.apply(kwargs={"batch_size": 50}).get()

    assert result == {
        "scanned": 5,
        "processed": 4,
        "failed": 1,
        "dead_lettered": 0,
    }
    assert "outcomes" not in result


def test_process_cdc_batch_default_batch_size() -> None:
    from app.workers.tasks import graphrag as task_mod

    captured: dict = {}

    async def _fake_run(batch_size: int = 100):
        captured["batch_size"] = batch_size
        return {"scanned": 0, "processed": 0, "failed": 0, "dead_lettered": 0}

    with patch.object(task_mod, "_run_dispatch", _fake_run):
        task_mod.process_cdc_batch.apply().get()

    assert captured["batch_size"] == 100


def test_process_cdc_batch_propagates_failures() -> None:
    from app.workers.tasks import graphrag as task_mod

    async def _boom(batch_size: int = 100):
        raise RuntimeError("dispatcher down")

    with patch.object(task_mod, "_run_dispatch", _boom):
        async_result = task_mod.process_cdc_batch.apply(kwargs={"batch_size": 10})

    # Celery captura la excepción en `result.get()` — eager + propagates.
    with pytest.raises(RuntimeError, match="dispatcher down"):
        async_result.get()


def test_process_cdc_batch_accepts_zero_results_dataset() -> None:
    """Si no hay rows pending, el task termina ok con conteos en cero."""
    from app.workers.tasks import graphrag as task_mod

    async def _fake_run(batch_size: int = 100):
        return {
            "scanned": 0,
            "processed": 0,
            "failed": 0,
            "dead_lettered": 0,
            "outcomes": [],
        }

    with patch.object(task_mod, "_run_dispatch", _fake_run):
        result = task_mod.process_cdc_batch.apply(kwargs={"batch_size": 100}).get()

    assert result["scanned"] == 0
    assert result["processed"] == 0
    assert result["failed"] == 0
    assert result["dead_lettered"] == 0
