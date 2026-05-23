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
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.comparator.interfaces import (
    CandidateMatch,
    ComparatorPort,
    ComparisonStats,
    ReverseImageSearchPort,
)

logger = logging.getLogger(__name__)

_VLM_UNCERTAIN_CONFIDENCE_THRESHOLD = Decimal("0.50")


# ---------------------------------------------------------------------------
# Adapter Fase 1 — RagOnly (activo)
# ---------------------------------------------------------------------------


class RagOnlyComparatorAdapter(ComparatorPort):
    """Adapter RAG puro — Fase 1 activo.

    Implementa el contrato :class:`ComparatorPort` usando sólo embedding ANN
    (pgvector) sobre ``competitor_listings``. No depende de Neo4j ni del KG.

    Args:
        session: AsyncSession inyectada para operaciones DB (Fase 1.5+).
                 None → confirm_match / reject_match son no-op (Fase 1).
    """

    def __init__(
        self,
        *,
        session: AsyncSession | None = None,
        ris_adapter: ReverseImageSearchPort | None = None,
    ) -> None:
        self._session = session
        self._ris_adapter = ris_adapter

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
        return []

    async def confirm_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Persiste decisión 'match' en match_decisions con columnas VLM (Fase 1.5+)."""
        logger.debug(
            "comparator.rag_only.confirm_match listing_id=%s product_sku=%s",
            listing_id,
            product_sku,
        )
        if self._session is None:
            logger.warning(
                "comparator.rag_only.confirm_match: no session — no-op listing_id=%s sku=%s",
                listing_id,
                product_sku,
            )
            return

        from app.db.models.comparator import MatchDecision
        from app.services.matching.human_queue_service import HumanQueueService

        # Idempotencia: bloquear cualquier decisión duplicada para este par
        existing_stmt = (
            select(MatchDecision.id)
            .where(MatchDecision.competitor_listing_id == listing_id)
            .where(MatchDecision.product_sku == product_sku)
            .limit(1)
        )
        existing = await self._session.execute(existing_stmt)
        if existing.scalar_one_or_none() is not None:
            logger.debug(
                "comparator.rag_only.confirm_match: idempotente — "
                "ya existe decisión listing_id=%s sku=%s",
                listing_id,
                product_sku,
            )
            return

        # Extraer datos VLM del evidence
        vlm_data: dict[str, Any] = (evidence or {}).get("vlm") or {}
        judge_verdict: str | None = None
        judge_confidence: Decimal | None = None
        judge_rationale: str | None = None
        judge_image_regions: list[dict[str, Any]] | None = None
        deal_breakers: list[str] | None = None
        judge_model_version: str | None = None
        if vlm_data:
            judge_verdict = vlm_data.get("verdict") or None
            judge_confidence_raw = vlm_data.get("confidence")
            judge_confidence = (
                Decimal(str(judge_confidence_raw)) if judge_confidence_raw is not None else None
            )
            judge_rationale = vlm_data.get("rationale")
            judge_image_regions = vlm_data.get("image_regions") or None
            deal_breakers = vlm_data.get("deal_breakers_triggered") or None
            judge_model_version = vlm_data.get("model_version")

        if judge_confidence is not None and not (Decimal("0") <= judge_confidence <= Decimal("1")):
            logger.warning(
                "comparator.rag_only.confirm_match: confidence fuera de rango [0,1] "
                "listing_id=%s confidence=%s — forzado a None",
                listing_id,
                judge_confidence,
            )
            judge_confidence = None

        decision = MatchDecision(
            competitor_listing_id=listing_id,
            product_sku=product_sku,
            decision="match",
            decided_by=decided_by,
            evidence_jsonb=evidence or {},
            judge_verdict=judge_verdict,
            judge_confidence=judge_confidence,
            judge_rationale=judge_rationale,
            judge_image_regions=judge_image_regions,
            deal_breakers_triggered=deal_breakers,
            judge_model_version=judge_model_version if judge_verdict is not None else None,
            judge_at=datetime.now(tz=UTC) if judge_verdict is not None else None,
        )
        self._session.add(decision)
        await self._session.flush()

        # RIS rescue — si confidence baja y hay ris_adapter (AC#1, #4, #5)
        calibrated_confidence_raw = (evidence or {}).get("calibrated_confidence")
        image_url = (evidence or {}).get("image_url")
        if (
            self._ris_adapter is not None
            and calibrated_confidence_raw is not None
            and image_url is not None
        ):
            cal_conf = Decimal(str(calibrated_confidence_raw))
            if cal_conf < _VLM_UNCERTAIN_CONFIDENCE_THRESHOLD:
                from app.db.models.comparator import CompetitorListing
                from app.services.image_search.ris_boost import (
                    apply_ris_boost,
                    get_canonical_domains,
                )

                ris_result = await self._ris_adapter.search(image_url=image_url)
                canonical_domains = await get_canonical_domains(
                    session=self._session, product_sku=product_sku
                )
                boosted_conf, was_boosted = apply_ris_boost(cal_conf, ris_result, canonical_domains)

                listing_stmt = select(CompetitorListing).where(CompetitorListing.id == listing_id)
                listing_row = (await self._session.execute(listing_stmt)).scalar_one_or_none()
                if listing_row is not None:
                    listing_row.reverse_image_hits = [
                        {"url": h.url, "domain": h.domain, "similarity": h.similarity}
                        for h in ris_result.hits
                    ]
                    listing_row.reverse_image_searched_at = ris_result.searched_at
                    listing_row.reverse_image_provider = ris_result.provider

                if was_boosted:
                    decision.confidence = boosted_conf
                    decision.evidence_jsonb = {
                        **(decision.evidence_jsonb or {}),
                        "ris": {
                            "provider": ris_result.provider,
                            "hits_count": len(ris_result.hits),
                            "boost_applied": True,
                        },
                        "method": "embedding+ris",
                    }

                await self._session.flush()

        # Routing automático a human queue si VLM incierto y confianza baja (AC#4)
        if judge_verdict == "uncertain" and judge_confidence is not None:
            if judge_confidence < _VLM_UNCERTAIN_CONFIDENCE_THRESHOLD:
                hqs = HumanQueueService(self._session)
                await hqs.enqueue_vlm_uncertain(
                    listing_id=listing_id,
                    product_sku=product_sku,
                    rationale=judge_rationale,
                    image_regions=judge_image_regions,
                )

    async def reject_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Persiste decisión 'no_match' en match_decisions con columnas VLM (Fase 1.5+)."""
        logger.debug(
            "comparator.rag_only.reject_match listing_id=%s product_sku=%s",
            listing_id,
            product_sku,
        )
        if self._session is None:
            logger.warning(
                "comparator.rag_only.reject_match: no session — no-op listing_id=%s sku=%s",
                listing_id,
                product_sku,
            )
            return

        from app.db.models.comparator import MatchDecision

        # Idempotencia: bloquear cualquier decisión duplicada para este par
        existing_stmt = (
            select(MatchDecision.id)
            .where(MatchDecision.competitor_listing_id == listing_id)
            .where(MatchDecision.product_sku == product_sku)
            .limit(1)
        )
        existing = await self._session.execute(existing_stmt)
        if existing.scalar_one_or_none() is not None:
            logger.debug(
                "comparator.rag_only.reject_match: idempotente — "
                "ya existe decisión listing_id=%s sku=%s",
                listing_id,
                product_sku,
            )
            return

        vlm_data: dict[str, Any] = (evidence or {}).get("vlm") or {}
        r_verdict: str | None = None
        r_rationale: str | None = None
        r_image_regions: list[dict[str, Any]] | None = None
        r_deal_breakers: list[str] | None = None
        r_model_version: str | None = None
        if vlm_data:
            r_verdict = vlm_data.get("verdict") or None
            r_rationale = vlm_data.get("rationale")
            r_image_regions = vlm_data.get("image_regions") or None
            r_deal_breakers = vlm_data.get("deal_breakers_triggered") or None
            r_model_version = vlm_data.get("model_version")

        decision = MatchDecision(
            competitor_listing_id=listing_id,
            product_sku=product_sku,
            decision="no_match",
            decided_by=decided_by,
            evidence_jsonb=evidence or {},
            judge_verdict=r_verdict,
            judge_confidence=None,
            judge_rationale=r_rationale,
            judge_image_regions=r_image_regions,
            deal_breakers_triggered=r_deal_breakers,
            judge_model_version=r_model_version if r_verdict is not None else None,
            judge_at=datetime.now(tz=UTC) if r_verdict is not None else None,
        )
        self._session.add(decision)
        await self._session.flush()

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
