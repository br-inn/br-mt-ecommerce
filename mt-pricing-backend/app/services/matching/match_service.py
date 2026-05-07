"""MatchService — orquestador del matching pipeline foundation.

Combina las piezas de Sprint 3:
1. :class:`QueryBuilder` produce queries multi-canal para el SKU.
2. Para cada fetcher registrado, ejecuta ``fetch`` con la primera query del
   canal correspondiente (los stubs ignoran la query → devuelven canned).
3. Cada candidato se puntúa con :func:`compute_scoring` (0-100).
4. Cada candidato se clasifica como ``peer`` (score ≥ 70) o ``drop`` /
   ``unknown`` según reglas heurísticas — el threshold es provisional para
   Sprint 3 y vivirá en ``comparator_config`` cuando exista.
5. Persistencia upsert vía :class:`MatchCandidateRepository`.

Errores de dominio se modelan como :class:`MatchDomainError` para que la capa
de routes los traduzca a HTTP 4xx (mismo patrón que ``ProductDomainError``).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.match_candidate import MatchCandidate
from app.repositories.matches import MatchCandidateRepository
from app.repositories.product import ProductRepository
from app.services.matching.adapters import (
    AmazonUaeStubFetcher,
    NoonUaeStubFetcher,
)
from app.services.matching.ports import CandidateRaw, FetcherPort
from app.services.matching.query_builder import QueryBuilder
from app.services.matching.scoring import compute_scoring

# Threshold provisional Sprint 3 — peer cuando score ≥ 70.
# TODO(ADR-MATCH-THRESHOLDS): externalizar a comparator_config.
PEER_SCORE_THRESHOLD = 70
DROP_SCORE_THRESHOLD = 40


class MatchDomainError(Exception):
    """Errores de negocio del matching service — mapean a 4xx en routes."""

    def __init__(self, code: str, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


class MatchSkuNotFoundError(MatchDomainError):
    def __init__(self, sku: str) -> None:
        super().__init__(
            code="match_sku_not_found",
            message=f"SKU {sku!r} no existe — no se pueden traer candidatos.",
            status_code=404,
        )


class MatchCandidateNotFoundError(MatchDomainError):
    def __init__(self, candidate_id: UUID | str) -> None:
        super().__init__(
            code="match_candidate_not_found",
            message=f"Match candidate {candidate_id!s} no existe.",
            status_code=404,
        )


class MatchInvalidTransitionError(MatchDomainError):
    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            code="match_invalid_transition",
            message=f"Transición {current!r} → {target!r} no permitida.",
            status_code=409,
        )


def _classify_candidate(score: int, scoring_notes: list[str]) -> str:
    """Clasifica el candidato como peer / drop / unknown.

    Heurística Sprint 3:
    - score ≥ 70 → ``peer`` (peer-group para G1).
    - 40 ≤ score < 70 → ``drop`` (no es el mismo producto, pero compite).
    - score < 40 o mismatch grave (PN / thread) → ``unknown``.
    """
    blocking = {"pn_below_sku_requirement", "thread_mismatch", "material_mismatch"}
    if blocking.intersection(scoring_notes):
        return "unknown"
    if score >= PEER_SCORE_THRESHOLD:
        return "peer"
    if score >= DROP_SCORE_THRESHOLD:
        return "drop"
    return "unknown"


class MatchService:
    """Orquesta query → fetch → score → upsert.

    El servicio recibe la sesión async y opcionalmente fetchers custom (para
    tests). Por defecto usa los stubs de Amazon UAE + Noon UAE.
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        fetchers: Sequence[FetcherPort] | None = None,
        query_builder: QueryBuilder | None = None,
    ) -> None:
        self.session = session
        self.fetchers: list[FetcherPort] = list(
            fetchers
            if fetchers is not None
            else (AmazonUaeStubFetcher(), NoonUaeStubFetcher())
        )
        self.query_builder = query_builder or QueryBuilder()
        self._matches_repo = MatchCandidateRepository(session)
        self._products_repo = ProductRepository(session)

    # ----------------------------------------------------------------------
    # Refresh
    # ----------------------------------------------------------------------
    async def refresh_candidates(self, sku: str) -> list[MatchCandidate]:
        """Etapa 1+2 stub + scoring + persistencia.

        Devuelve los candidatos ya persistidos (orden por score DESC).
        """
        product = await self._products_repo.get_by_sku(sku)
        if product is None:
            raise MatchSkuNotFoundError(sku)

        sku_dict = self._product_to_dict(product)
        queries = self.query_builder.build_for_sku(sku_dict)

        persisted: list[MatchCandidate] = []
        for fetcher in self.fetchers:
            channel_queries = [q for q in queries if q.source == fetcher.channel]
            if not channel_queries:
                continue
            # Stub: usamos sólo la primera query (el adapter real iteraría)
            primary = channel_queries[0]
            candidates_raw = await fetcher.fetch(primary, sku=sku)
            for raw in candidates_raw:
                row = await self._score_and_upsert(sku_dict, raw)
                persisted.append(row)

        # Sort por score DESC (best first), estable.
        persisted.sort(key=lambda r: r.score, reverse=True)
        return persisted

    async def _score_and_upsert(
        self, sku_dict: dict[str, Any], raw: CandidateRaw
    ) -> MatchCandidate:
        cand_dict: dict[str, Any] = {
            "brand": raw.brand,
            "price_aed": raw.price_aed,
            "delivery_text": raw.delivery_text,
            "specs": dict(raw.specs),
        }
        # Aplastamos specs al top-level para que `compute_scoring` los lea.
        for k, v in (raw.specs or {}).items():
            cand_dict.setdefault(k, v)

        breakdown = compute_scoring(sku_dict, cand_dict)
        kind = _classify_candidate(breakdown.score, breakdown.notes)

        # Persistir el breakdown completo como parte del JSONB para auditoría.
        specs_to_persist = dict(raw.specs)
        specs_to_persist["_scoring"] = breakdown.as_dict()

        return await self._matches_repo.upsert_candidate(
            product_sku=str(sku_dict.get("sku")),
            channel=raw.source,
            external_id=raw.external_id,
            title=raw.title,
            brand=raw.brand,
            price_aed=raw.price_aed,
            delivery_text=raw.delivery_text,
            specs_jsonb=specs_to_persist,
            kind=kind,
            score=breakdown.score,
        )

    # ----------------------------------------------------------------------
    # Listing / detail
    # ----------------------------------------------------------------------
    async def list_candidates(
        self,
        *,
        sku: str | None = None,
        status: str | None = None,
        channel: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
    ) -> tuple[Sequence[MatchCandidate], UUID | None]:
        return await self._matches_repo.list_with_filters(
            sku=sku, status=status, channel=channel, cursor=cursor, limit=limit
        )

    async def get_candidate(self, candidate_id: UUID) -> MatchCandidate:
        obj = await self._matches_repo.get(candidate_id)
        if obj is None:
            raise MatchCandidateNotFoundError(candidate_id)
        return obj

    # ----------------------------------------------------------------------
    # State transitions
    # ----------------------------------------------------------------------
    async def validate_candidate(
        self, candidate_id: UUID, *, user_id: UUID | None
    ) -> MatchCandidate:
        obj = await self.get_candidate(candidate_id)
        if obj.status == "discarded":
            raise MatchInvalidTransitionError(obj.status, "validated")
        updated = await self._matches_repo.mark_validated(
            candidate_id, user_id=user_id
        )
        assert updated is not None  # acabamos de leer el row
        return updated

    async def discard_candidate(
        self, candidate_id: UUID, *, reason: str | None = None
    ) -> MatchCandidate:
        obj = await self.get_candidate(candidate_id)
        if obj.status == "validated":
            raise MatchInvalidTransitionError(obj.status, "discarded")
        updated = await self._matches_repo.mark_discarded(candidate_id, reason=reason)
        assert updated is not None
        return updated

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    @staticmethod
    def _product_to_dict(product: Any) -> dict[str, Any]:
        """Extrae los campos relevantes para el matching de un Product ORM o dict."""
        if isinstance(product, dict):
            base = dict(product)
        else:
            base = {
                "sku": getattr(product, "sku", None),
                "name_en": getattr(product, "name_en", None),
                "family": getattr(product, "family", None),
                "subfamily": getattr(product, "subfamily", None),
                "material": getattr(product, "material", None),
                "dn": getattr(product, "dn", None),
                "pn": getattr(product, "pn", None),
                "connection": getattr(product, "connection", None),
                "brand": getattr(product, "brand", None),
                "specs": dict(getattr(product, "specs", {}) or {}),
            }
        # Alias `thread` ⇄ `connection` para que scoring lea ambos.
        if base.get("thread") is None and base.get("connection") is not None:
            base["thread"] = base["connection"]
        return base
