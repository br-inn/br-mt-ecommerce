"""Product comparison / matching pipeline — research workstream (ADR-012).

Fase 1 deja sólo hooks: tablas vacías (``competitor_listings``,
``match_decisions``), interfaces hexagonales (OCR / RIS / VLM judge /
comparator) y :class:`NoopComparatorService` que satisface el contrato
sin hacer nada.

Para activar la implementación real (Fase 1.5+):

1. Implementar ``ProductComparisonService(ComparatorPort)`` componiendo
   los puertos OCR / RIS / VLM + embedding ANN.
2. Registrar en :class:`ComparatorServiceFactory.create`.
3. Activar flag ``COMPARATOR_ENABLED`` vía ``/admin/flags``.
"""

from __future__ import annotations

from app.services.comparator.adapters import (
    FullGraphRagComparatorAdapter,
    HybridComparatorAdapter,
    RagOnlyComparatorAdapter,
)
from app.services.comparator.factory import (
    FLAG_COMPARATOR_ENABLED,
    ComparatorServiceFactory,
)
from app.services.comparator.graph_repository import (
    GraphRepository,
    Neo4jGraphRepository,
    PostgresGraphRepository,
    get_graph_repository,
)
from app.services.comparator.interfaces import (
    CandidateMatch,
    ComparatorPort,
    ComparisonStats,
    OcrBlock,
    OcrPort,
    OcrResult,
    ReverseImageHit,
    ReverseImageSearchPort,
    ReverseImageSearchResult,
    VlmJudgePort,
    VlmJudgeVerdict,
)
from app.services.comparator.noop_service import (
    DISABLED_WARNING,
    NoopComparatorService,
)

__all__ = [
    "DISABLED_WARNING",
    "FLAG_COMPARATOR_ENABLED",
    "CandidateMatch",
    "ComparatorPort",
    "ComparatorServiceFactory",
    "ComparisonStats",
    "FullGraphRagComparatorAdapter",
    "GraphRepository",
    "HybridComparatorAdapter",
    "Neo4jGraphRepository",
    "NoopComparatorService",
    "OcrBlock",
    "OcrPort",
    "OcrResult",
    "PostgresGraphRepository",
    "RagOnlyComparatorAdapter",
    "ReverseImageHit",
    "ReverseImageSearchPort",
    "ReverseImageSearchResult",
    "VlmJudgePort",
    "VlmJudgeVerdict",
    "get_graph_repository",
]
