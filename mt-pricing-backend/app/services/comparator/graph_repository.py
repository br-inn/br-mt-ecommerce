"""GraphRepository — abstracción de persistencia de grafo para el comparator.

US-RND-01-11 / FR-CMP-GRAPH-01:

Permite introducir Neo4j en Fase 2+ sin refactor del comparator service.
Fase 1 usa :class:`PostgresGraphRepository` (activo), que persiste el grafo
en tablas relacionales Postgres ya existentes (``products``,
``competitor_listings``, ``match_decisions``).

Fase 2+ swapea a :class:`Neo4jGraphRepository` vía ``GRAPHRAG_BACKEND=neo4j``
delegando al :class:`GraphStorePort` ya implementado.

Diferencia con :class:`GraphStorePort` (``app.services.graphrag.ports``):

- ``GraphStorePort`` es una abstracción genérica de operaciones de grafo
  (merge_node, merge_edge, query_neighbors…).
- ``GraphRepository`` es un repositorio de dominio específico del comparator:
  expone operaciones de alto nivel como ``get_product_neighbors`` y
  ``get_competitor_context`` que hablan el lenguaje del negocio, no del grafo.

Patrón: ports-and-adapters (ver ``app.services.channel_mirror.ports``).
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any
from uuid import UUID

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Port (interfaz abstracta)
# ---------------------------------------------------------------------------

class GraphRepository(ABC):
    """Puerto de repositorio de grafo para el subsistema de comparación.

    Operaciones de dominio sobre el grafo de productos / competidores. El
    caller (comparator adapters) nunca accede a Postgres ni Neo4j directamente
    — siempre via este puerto.

    Fase 1: implementación activa es :class:`PostgresGraphRepository`.
    Fase 2+: swap a :class:`Neo4jGraphRepository` (``GRAPHRAG_BACKEND=neo4j``).
    """

    @abstractmethod
    async def get_product_neighbors(
        self,
        product_sku: str,
        *,
        relationship_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Devuelve nodos vecinos de un producto en el grafo.

        Args:
            product_sku: SKU del producto MT origen.
            relationship_type: filtro opcional (e.g. ``'SUPPLIED_BY'``,
                ``'HAS_MATCH'``). ``None`` = todos los tipos.

        Returns:
            Lista de dicts ``{node_type, node_id, properties, relationship}``.

        Fase 1: consulta relaciones en tablas Postgres (suppliers, etc.).
        Fase 2+: MATCH Cypher en Neo4j.
        """

    @abstractmethod
    async def get_competitor_context(
        self,
        competitor_listing_id: UUID,
    ) -> dict[str, Any]:
        """Recupera contexto de grafo para un competitor listing.

        Args:
            competitor_listing_id: ID del competitor listing.

        Returns:
            Dict con contexto enriquecido (product_matches, supplier_hints,
            graph_confidence…).

        Fase 1: consulta ``match_decisions`` + ``competitor_listings``
        relacionales.
        Fase 2+: traversal Neo4j para contexto enriquecido de KG.
        """

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Estado operativo del repositorio (para /health endpoints)."""


# ---------------------------------------------------------------------------
# PostgresGraphRepository — activo Fase 1
# ---------------------------------------------------------------------------

class PostgresGraphRepository(GraphRepository):
    """Repositorio de grafo sobre Postgres relacional.

    Fase 1 activo. Usa las tablas existentes (``products``,
    ``competitor_listings``, ``match_decisions``) como un grafo implícito.
    No requiere Neo4j.

    En Fase 1 las tablas del comparator están vacías, por lo que todos los
    métodos devuelven resultados vacíos. La infraestructura queda preparada
    para Fase 1.5+ sin refactor.

    Args:
        session_factory: callable que devuelve un ``AsyncSession`` de
            SQLAlchemy. Inyectado vía DI. Si es ``None``, opera en modo
            degradado (devuelve siempre vacío) — útil para tests sin DB.
    """

    def __init__(self, session_factory: Any = None) -> None:
        self._session_factory = session_factory

    async def get_product_neighbors(
        self,
        product_sku: str,
        *,
        relationship_type: str | None = None,
    ) -> list[dict[str, Any]]:
        """Vecinos de un producto via relaciones Postgres.

        Fase 1: devuelve lista vacía (tablas sin datos; consulta real en
        Fase 1.5+).
        """
        logger.debug(
            "graph_repo.postgres.get_product_neighbors sku=%s rel=%s",
            product_sku,
            relationship_type,
        )
        # Fase 1.5+:
        # async with self._session_factory() as session:
        #     rows = await session.execute(
        #         select(SupplierProduct).where(SupplierProduct.product_sku == product_sku)
        #     )
        #     return [{"node_type": "Supplier", ...} for r in rows]
        return []

    async def get_competitor_context(
        self,
        competitor_listing_id: UUID,
    ) -> dict[str, Any]:
        """Contexto relacional de un competitor listing.

        Fase 1: devuelve dict vacío (tablas sin datos).
        """
        logger.debug(
            "graph_repo.postgres.get_competitor_context listing_id=%s",
            competitor_listing_id,
        )
        # Fase 1.5+: JOIN competitor_listings + match_decisions + products
        return {
            "competitor_listing_id": str(competitor_listing_id),
            "product_matches": [],
            "supplier_hints": [],
            "graph_confidence": 0.0,
        }

    async def health_check(self) -> dict[str, Any]:
        return {
            "backend": "postgres_graph_repository",
            "healthy": True,
            "note": "Fase 1 — tablas vacías; consultas reales en Fase 1.5+",
        }


# ---------------------------------------------------------------------------
# Neo4jGraphRepository — stub Fase 2+
# ---------------------------------------------------------------------------

_NEO4J_NOT_IMPLEMENTED = (
    "Neo4jGraphRepository no está activo en Fase 1. "
    "Activar en Fase 2+ configurando GRAPHRAG_BACKEND=neo4j."
)


class Neo4jGraphRepository(GraphRepository):
    """Repositorio de grafo sobre Neo4j 5 (stub Fase 2+).

    Delega en :class:`GraphStorePort` (``app.services.graphrag.ports``)
    que ya tiene implementaciones real + stub (ADR-016).

    En Fase 1 todos los métodos lanzan :exc:`NotImplementedError` como señal
    explícita de «no usar directamente». El factory nunca instancia este
    repositorio con ``GRAPHRAG_BACKEND=stub`` (default).
    """

    def __init__(self, graph_store: Any = None) -> None:
        """Args:
            graph_store: instancia de :class:`GraphStorePort` (Neo4jGraphStore
                real o Neo4jStubGraphStore para tests). Inyectado vía factory.
        """
        self._graph_store = graph_store

    async def get_product_neighbors(
        self,
        product_sku: str,
        *,
        relationship_type: str | None = None,
    ) -> list[dict[str, Any]]:
        raise NotImplementedError(_NEO4J_NOT_IMPLEMENTED)

    async def get_competitor_context(
        self,
        competitor_listing_id: UUID,
    ) -> dict[str, Any]:
        raise NotImplementedError(_NEO4J_NOT_IMPLEMENTED)

    async def health_check(self) -> dict[str, Any]:
        return {
            "backend": "neo4j_graph_repository",
            "healthy": False,
            "note": "Stub Fase 1 — activar en Fase 2+ con GRAPHRAG_BACKEND=neo4j",
        }


# ---------------------------------------------------------------------------
# Factory helper
# ---------------------------------------------------------------------------

def get_graph_repository(session_factory: Any = None) -> GraphRepository:
    """Devuelve el :class:`GraphRepository` activo según ``GRAPHRAG_BACKEND``.

    - ``stub`` (default): :class:`PostgresGraphRepository`.
    - ``neo4j``: :class:`Neo4jGraphRepository` delegando al ``GraphStorePort``.
    """
    try:
        from app.core.config import settings
        backend = settings.GRAPHRAG_BACKEND
    except Exception:  # noqa: BLE001 — config opcional en tests
        backend = "stub"

    if backend == "neo4j":
        try:
            from app.services.graphrag.adapters.factory import get_default_graph_store
            graph_store = get_default_graph_store()
        except Exception:  # noqa: BLE001
            graph_store = None
        return Neo4jGraphRepository(graph_store=graph_store)

    return PostgresGraphRepository(session_factory=session_factory)


__all__ = [
    "GraphRepository",
    "Neo4jGraphRepository",
    "PostgresGraphRepository",
    "get_graph_repository",
]
