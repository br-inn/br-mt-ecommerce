"""Ports (interfaces) del subsistema de comparación de productos.

Hexagonal — los adapters reales (OCR, RIS, VLM judge) se inyectan vía
:class:`ComparatorServiceFactory` en Fase 1.5+. Fase 1 deja sólo las
firmas abstractas + :class:`NoopComparatorService` como fallback.

Ver:
- ADR-012 (comparator como research workstream).
- ADR-022 (OCR), ADR-023 (reverse image search), ADR-024 (VLM judge):
  proposed, NO activados Fase 1.
- architecture-mt-pricing-mdm-phase1.md §17.1.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


# ---------------------------------------------------------------------------
# DTOs (lightweight) — los modelos ORM viven en app.db.models.comparator
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class OcrBlock:
    """Bloque OCR — bounding box + texto + confidence."""

    text: str
    confidence: float  # 0..1
    bbox: tuple[float, float, float, float]  # (x, y, w, h)
    language: str | None = None


@dataclass(frozen=True)
class OcrResult:
    """Resultado de OCR sobre una imagen de listing."""

    provider: str  # 'google_vision' | 'tesseract' | 'aws_textract' | ...
    ocr_text: str
    blocks: tuple[OcrBlock, ...]
    languages_detected: tuple[str, ...]
    extracted_at: datetime


@dataclass(frozen=True)
class ReverseImageHit:
    """Hit de reverse image search."""

    url: str
    domain: str
    similarity: float  # 0..1 (si el proveedor lo da, sino 0.0)
    thumbnail_url: str | None = None
    title: str | None = None


@dataclass(frozen=True)
class ReverseImageSearchResult:
    provider: str  # 'tineye' | 'google_lens_serpapi' | 'bing_visual'
    hits: tuple[ReverseImageHit, ...]
    searched_at: datetime


@dataclass(frozen=True)
class VlmJudgeVerdict:
    """Veredicto VLM judge — qué dice el modelo cuando compara dos imágenes."""

    decision: str  # 'match' | 'no_match' | 'uncertain'
    confidence: float  # 0..1
    rationale: str
    deal_breakers_triggered: tuple[str, ...] = ()


@dataclass(frozen=True)
class CandidateMatch:
    """Candidato match SKU MT ↔ competitor listing.

    El score es post-calibración (Platt / isotonic / conformal — research
    workstream firma el método en S5+).
    """

    competitor_listing_id: UUID
    product_sku: str
    score: Decimal
    method: str  # 'embedding' | 'embedding+ocr' | 'embedding+ris' | 'vlm' | ...
    evidence: dict[str, Any]


@dataclass(frozen=True)
class ComparisonStats:
    """Snapshot de cobertura/decisiones del comparator (admin)."""

    listings_total: int
    listings_with_match: int
    decisions_pending: int
    decisions_confirmed: int
    decisions_rejected: int


# ---------------------------------------------------------------------------
# Ports
# ---------------------------------------------------------------------------
class OcrPort(ABC):
    """Puerto OCR — extrae texto + bounding boxes de una imagen de listing.

    Adapter por defecto Fase 1.5+: Google Vision (DOCUMENT_TEXT_DETECTION).
    Fallback offline: Tesseract.
    """

    @abstractmethod
    async def extract_text(
        self,
        *,
        listing_id: UUID,
        image_url: str,
    ) -> OcrResult:
        """Extrae texto OCR de ``image_url``.

        Contrato:
            - Resultado idempotente para misma image_url + provider.
            - Caller persiste en ``competitor_listing_ocr`` (Fase 1.5+).
            - Costos por llamada → llamar sólo sobre top-N candidatos.
        """


class ReverseImageSearchPort(ABC):
    """Puerto reverse image search.

    Sólo se invoca cuando ``calibrated_confidence < 0.50`` (ADR-023) para
    acotar coste. Si una URL hit pertenece al dominio del fabricante
    canónico (whitelist ``manufacturers.canonical_domain``), re-disparar
    scoring puede confirmar el match.
    """

    @abstractmethod
    async def search(
        self,
        *,
        image_url: str,
        max_results: int = 10,
    ) -> ReverseImageSearchResult:
        """Busca apariciones de la imagen en la web abierta."""


class VlmJudgePort(ABC):
    """Puerto VLM judge — modelo visión que decide match/no_match/uncertain.

    Adapter Fase 1.5+: GPT-4o vision / Claude vision / Gemini. Sólo se
    invoca sobre el top-N (default 3) candidatos por SKU para acotar coste.
    El veredicto se persiste en ``match_decisions.evidence_jsonb`` para
    auditoría completa (ADR-024).
    """

    @abstractmethod
    async def judge(
        self,
        *,
        product_sku: str,
        candidate_image_url: str,
        product_image_url: str,
        context: dict[str, Any],
    ) -> VlmJudgeVerdict:
        """Compara imagen de catálogo MT vs imagen candidato.

        ``context`` lleva specs estructuradas (DN, PN, material) como hint
        al modelo: una diferencia de DN es un deal-breaker que el modelo
        debe respetar incluso si las imágenes parecen iguales.
        """


class ComparatorPort(ABC):
    """Puerto orquestador del subsistema de comparación.

    API pública consumida por el resto del backend (workers, API routes).
    Fase 1: única implementación es :class:`NoopComparatorService`.
    Fase 1.5+: ``ProductComparisonService`` real que compone los puertos
    OCR / RIS / VLM judge + embedding ANN.
    """

    @abstractmethod
    async def find_candidates(
        self,
        *,
        product_sku: str,
        limit: int = 10,
    ) -> list[CandidateMatch]:
        """Busca candidatos competitor listings para un SKU MT.

        Fase 1 (stub): devuelve ``[]`` (research no ha entregado).
        Fase 1.5+ (real): embedding ANN sobre ``competitor_listings`` +
        scoring multi-dimensional + reglas duras (DN, PN, material).
        """

    @abstractmethod
    async def confirm_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Persiste decisión humana 'match' en ``match_decisions``."""

    @abstractmethod
    async def reject_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        """Persiste decisión humana 'no_match' en ``match_decisions``."""

    @abstractmethod
    async def get_stats(self) -> ComparisonStats:
        """Snapshot de cobertura/decisiones (admin / dashboard)."""


__all__ = [
    "CandidateMatch",
    "ComparatorPort",
    "ComparisonStats",
    "OcrBlock",
    "OcrPort",
    "OcrResult",
    "ReverseImageHit",
    "ReverseImageSearchPort",
    "ReverseImageSearchResult",
    "VlmJudgePort",
    "VlmJudgeVerdict",
]
