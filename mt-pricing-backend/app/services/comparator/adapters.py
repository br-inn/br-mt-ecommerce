"""Comparator adapter implementations (US-RND-01-11 / FR-CMP-GRAPH-01).

Tres adapters estratificados que implementan :class:`ComparatorPort`:

- :class:`RagOnlyComparatorAdapter` — activo Fase 1.  Solo embedding ANN
  contra ``competitor_listings``. No requiere Neo4j ni KG.
- :class:`HybridComparatorAdapter` — stub Fase 2.  RAG + hints del KG
  Postgres (grafos relacionales ligeros). No activo Fase 1; lanza
  ``NotImplementedError`` si alguien lo invoca directamente.
- :class:`FullGraphRagComparatorAdapter` — stub Fase 2+.  KG Neo4j completo
  + RAG. No activo Fase 1; lanza ``NotImplementedError``.

Swap vía ``COMPARATOR_ADAPTER=rag_only|hybrid|full_graph_rag`` (settings)
sin tocar endpoints de API — basta con :func:`ComparatorServiceFactory.create`.

Patrón mirror de :mod:`app.services.channel_mirror.ports` (ports-and-adapters).
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from app.services.comparator.interfaces import (
    CandidateMatch,
    ComparatorPort,
    ComparisonStats,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Adapter Fase 1 — RagOnly (activo)
# ---------------------------------------------------------------------------

class RagOnlyComparatorAdapter(ComparatorPort):
    """Adapter RAG puro — Fase 1 activo.

    Implementa el contrato :class:`ComparatorPort` usando sólo embedding ANN
    (pgvector) sobre ``competitor_listings``. No depende de Neo4j ni del KG.

    En Fase 1 la tabla ``competitor_listings`` está vacía, por lo que todos
    los métodos devuelven resultados vacíos / no-op. La infraestructura queda
    lista para Fase 1.5+ sin refactor: basta con poblar la tabla y activar el
    flag ``COMPARATOR_ENABLED``.
    """

    async def find_candidates(
        self,
        *,
        product_sku: str,
        limit: int = 10,
    ) -> list[CandidateMatch]:
        """Embedding ANN contra competitor_listings (Fase 1: tabla vacía → [])."""
        logger.debug(
            "comparator.rag_only.find_candidates product_sku=%s limit=%d",
            product_sku,
            limit,
        )
        # Fase 1.5+: SELECT embedding <=> $vec FROM competitor_listings
        # ORDER BY embedding <=> $vec LIMIT $limit
        # Por ahora devuelve lista vacía (tabla sin datos).
        return []

    async def confirm_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Persiste decisión 'match' (Fase 1: no-op — tabla match_decisions vacía)."""
        logger.debug(
            "comparator.rag_only.confirm_match listing_id=%s product_sku=%s",
            listing_id,
            product_sku,
        )
        # Fase 1.5+: INSERT INTO match_decisions ...

    async def reject_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Persiste decisión 'no_match' (Fase 1: no-op)."""
        logger.debug(
            "comparator.rag_only.reject_match listing_id=%s product_sku=%s",
            listing_id,
            product_sku,
        )
        # Fase 1.5+: INSERT INTO match_decisions ...

    async def get_stats(self) -> ComparisonStats:
        """Estadísticas de cobertura (Fase 1: contadores a 0)."""
        logger.debug("comparator.rag_only.get_stats")
        return ComparisonStats(
            listings_total=0,
            listings_with_match=0,
            decisions_pending=0,
            decisions_confirmed=0,
            decisions_rejected=0,
        )


# ---------------------------------------------------------------------------
# Adapter Fase 2 — Hybrid (stub)
# ---------------------------------------------------------------------------

_HYBRID_NOT_IMPLEMENTED = (
    "HybridComparatorAdapter no está activo en Fase 1. "
    "Activar en Fase 2 cuando el KG Postgres esté poblado."
)


class HybridComparatorAdapter(ComparatorPort):
    """Stub Fase 2 — RAG + graph hints Postgres.

    Combina embedding ANN con hints del grafo relacional (Postgres) para
    mejorar precision/recall sin depender de Neo4j. Activo en Fase 2.

    En Fase 1 todos los métodos lanzan :exc:`NotImplementedError` como señal
    explícita de «no usar directamente». El factory nunca instancia este
    adapter con ``COMPARATOR_ADAPTER=rag_only`` (default).
    """

    async def find_candidates(
        self,
        *,
        product_sku: str,
        limit: int = 10,
    ) -> list[CandidateMatch]:
        raise NotImplementedError(_HYBRID_NOT_IMPLEMENTED)

    async def confirm_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError(_HYBRID_NOT_IMPLEMENTED)

    async def reject_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError(_HYBRID_NOT_IMPLEMENTED)

    async def get_stats(self) -> ComparisonStats:
        raise NotImplementedError(_HYBRID_NOT_IMPLEMENTED)


# ---------------------------------------------------------------------------
# Adapter Fase 2+ — FullGraphRag (stub)
# ---------------------------------------------------------------------------

_FULL_GRAPH_NOT_IMPLEMENTED = (
    "FullGraphRagComparatorAdapter no está activo en Fase 1. "
    "Activar en Fase 2+ cuando Neo4j KG esté operativo."
)


class FullGraphRagComparatorAdapter(ComparatorPort):
    """Stub Fase 2+ — KG Neo4j completo + RAG.

    Orquesta el pipeline completo: embedding ANN → graph traversal Neo4j →
    OCR / RIS / VLM judge (ADR-012). Activo en Fase 2+.

    En Fase 1 todos los métodos lanzan :exc:`NotImplementedError`.
    """

    async def find_candidates(
        self,
        *,
        product_sku: str,
        limit: int = 10,
    ) -> list[CandidateMatch]:
        raise NotImplementedError(_FULL_GRAPH_NOT_IMPLEMENTED)

    async def confirm_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError(_FULL_GRAPH_NOT_IMPLEMENTED)

    async def reject_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        raise NotImplementedError(_FULL_GRAPH_NOT_IMPLEMENTED)

    async def get_stats(self) -> ComparisonStats:
        raise NotImplementedError(_FULL_GRAPH_NOT_IMPLEMENTED)


__all__ = [
    "FullGraphRagComparatorAdapter",
    "HybridComparatorAdapter",
    "RagOnlyComparatorAdapter",
]
