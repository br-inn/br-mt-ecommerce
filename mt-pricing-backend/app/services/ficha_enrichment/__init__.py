from __future__ import annotations
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.ficha_enrichment.extractor import FichaEnrichmentExtractor
    from app.services.ficha_enrichment.differ import FichaEnrichmentDiffer
    from app.services.ficha_enrichment.applier import FichaEnrichmentApplier


def __getattr__(name: str):
    if name == "FichaEnrichmentExtractor":
        from app.services.ficha_enrichment.extractor import FichaEnrichmentExtractor
        return FichaEnrichmentExtractor
    if name == "FichaEnrichmentDiffer":
        from app.services.ficha_enrichment.differ import FichaEnrichmentDiffer
        return FichaEnrichmentDiffer
    if name == "FichaEnrichmentApplier":
        from app.services.ficha_enrichment.applier import FichaEnrichmentApplier
        return FichaEnrichmentApplier
    raise AttributeError(name)


__all__ = ["FichaEnrichmentExtractor", "FichaEnrichmentDiffer", "FichaEnrichmentApplier"]
