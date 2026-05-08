"""Graph store factory — selecciona stub vs Neo4j real según settings.

Single point of truth para resolver `GraphStorePort`:

- ``settings.GRAPHRAG_BACKEND == 'stub'`` (default): in-memory stub Fase 1.
- ``settings.GRAPHRAG_BACKEND == 'neo4j'``: driver real contra Neo4j 5.

El driver Neo4j es un singleton process-wide — se inicializa en la primera
llamada a :func:`get_default_graph_store` y se cierra en :func:`shutdown`
(invocado desde el lifespan de FastAPI).

Tests overrideán via :func:`set_default_graph_store` (existe en el stub
para fixtures unit; el factory respeta override siempre que esté seteado).
"""

from __future__ import annotations

import logging
import threading
from typing import TYPE_CHECKING

from app.core.config import settings
from app.services.graphrag.adapters.neo4j_stub import (
    Neo4jStubGraphStore,
    get_default_graph_store as _get_stub,
    set_default_graph_store as _set_stub,
)
from app.services.graphrag.ports import GraphStorePort

if TYPE_CHECKING:  # pragma: no cover
    from neo4j import Driver

logger = logging.getLogger(__name__)


_lock = threading.RLock()
_neo4j_driver: "Driver | None" = None
_neo4j_store: GraphStorePort | None = None
_override: GraphStorePort | None = None


def _build_neo4j_driver() -> "Driver":
    """Inicializa el driver Neo4j desde settings. Lazy import."""
    from neo4j import GraphDatabase

    return GraphDatabase.driver(
        settings.NEO4J_URI,
        auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD.get_secret_value()),
        connection_timeout=settings.NEO4J_CONNECTION_TIMEOUT_S,
        max_connection_pool_size=settings.NEO4J_MAX_CONNECTION_POOL_SIZE,
    )


def _get_neo4j_store() -> GraphStorePort:
    global _neo4j_driver, _neo4j_store
    with _lock:
        if _neo4j_store is None:
            from app.services.graphrag.adapters.neo4j_real import Neo4jGraphStore

            _neo4j_driver = _build_neo4j_driver()
            _neo4j_store = Neo4jGraphStore(
                _neo4j_driver,
                database=settings.NEO4J_DATABASE,
            )
            logger.info(
                "graphrag.factory.neo4j_initialized",
                extra={
                    "uri": settings.NEO4J_URI,
                    "database": settings.NEO4J_DATABASE,
                },
            )
        return _neo4j_store


def get_default_graph_store() -> GraphStorePort:
    """Devuelve el graph store activo según settings.

    Override (tests) tiene prioridad. Luego decide por
    ``settings.GRAPHRAG_BACKEND``.
    """
    if _override is not None:
        return _override
    if settings.GRAPHRAG_BACKEND == "neo4j":
        return _get_neo4j_store()
    return _get_stub()


def set_default_graph_store(store: GraphStorePort | None) -> None:
    """Override del graph store — usado en tests / fixtures.

    Pasar ``None`` resetea el override (vuelve a la decisión por settings).
    También resetea el singleton del stub para no leakear state entre tests.
    """
    global _override
    _override = store
    # Reset stub singleton también — facilita aislamiento de tests.
    if isinstance(store, Neo4jStubGraphStore) or store is None:
        _set_stub(store if isinstance(store, Neo4jStubGraphStore) else None)


def shutdown() -> None:
    """Cierra el driver Neo4j si está abierto. Llamar desde FastAPI lifespan."""
    global _neo4j_driver, _neo4j_store
    with _lock:
        if _neo4j_driver is not None:
            try:
                _neo4j_driver.close()
            except Exception as exc:  # noqa: BLE001
                logger.warning("graphrag.factory.shutdown_failed: %s", exc)
            _neo4j_driver = None
            _neo4j_store = None


__all__ = [
    "get_default_graph_store",
    "set_default_graph_store",
    "shutdown",
]
