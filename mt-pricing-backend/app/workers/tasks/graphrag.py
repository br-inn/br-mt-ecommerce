"""Tasks para la queue `comparator` — GraphRAG CDC dispatcher (US-RND-01-11).

Patrón:
- ``mt.graphrag.process_cdc_batch`` corre cada N segundos (configurable via
  job_definitions cuando US-1A-08-* salga). Por ahora es invocable manual
  o desde ``apply()`` sincrónico en tests.
- Construye un `AsyncSession` propio (las tasks Celery no comparten la
  request scope de FastAPI) y delega en `CdcDispatcher.process_batch`.
- El graph store se resuelve via :func:`get_default_graph_store` del
  factory — stub in-memory o Neo4j real según ``GRAPHRAG_BACKEND``.
"""

from __future__ import annotations

import asyncio
from typing import Any

import structlog

from app.services.graphrag.adapters import get_default_graph_store
from app.services.graphrag.cdc_dispatcher import CdcDispatcher
from app.workers.worker import celery_app

logger = structlog.get_logger(__name__)


async def _run_dispatch(batch_size: int) -> dict[str, Any]:
    """Helper async — abre session, despacha batch, commit."""
    from app.db import get_sessionmaker

    session_factory = get_sessionmaker()
    async with session_factory() as session:
        async with session.begin():
            graph = get_default_graph_store()
            dispatcher = CdcDispatcher(session, graph)
            result = await dispatcher.process_batch(batch_size=batch_size)
        return result


@celery_app.task(name="mt.graphrag.process_cdc_batch", bind=True)
def process_cdc_batch(self, batch_size: int = 100) -> dict[str, Any]:  # noqa: ANN001
    """Procesa hasta ``batch_size`` rows pending de ``cdc_events``."""
    try:
        result = asyncio.run(_run_dispatch(batch_size=batch_size))
    except Exception as exc:  # noqa: BLE001
        logger.exception("graphrag.cdc.batch.failed", error=str(exc))
        raise
    logger.info("graphrag.cdc.batch.ok", **result)
    return {
        k: v for k, v in result.items() if k != "outcomes"
    }  # outcomes puede ser grande — log debug only


__all__ = ["process_cdc_batch"]
