"""NoopComparatorService — implementación stub Fase 1 (ADR-012).

Fase 1 deja **toda** la lógica del comparator deshabilitada. Esta clase
satisface el :class:`ComparatorPort` devolviendo:

- ``find_candidates``  → ``[]``
- ``confirm_match`` / ``reject_match`` → no-op (no escribe en DB).
- ``get_stats``        → ``ComparisonStats`` con contadores a 0.

Cada llamada loggea un ``WARNING`` con el mensaje canónico
"comparator deshabilitado (research workstream)" para que cualquier
caller en Fase 1 que intente usarlo deje rastro audit.

Fase 1.5+: sustituir por ``ProductComparisonService`` real vía factory.
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

# Mensaje canónico — tests asertan contra esta cadena exacta.
DISABLED_WARNING = "comparator deshabilitado (research workstream)"


class NoopComparatorService(ComparatorPort):
    """Stub Fase 1 — todas las operaciones son no-op + WARNING."""

    async def find_candidates(
        self,
        *,
        product_sku: str,
        limit: int = 10,
    ) -> list[CandidateMatch]:
        logger.warning(
            DISABLED_WARNING,
            extra={"op": "find_candidates", "product_sku": product_sku},
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
        logger.warning(
            DISABLED_WARNING,
            extra={
                "op": "confirm_match",
                "listing_id": str(listing_id),
                "product_sku": product_sku,
            },
        )
        return None

    async def reject_match(
        self,
        *,
        listing_id: UUID,
        product_sku: str,
        decided_by: UUID,
        evidence: dict[str, Any] | None = None,
    ) -> None:
        logger.warning(
            DISABLED_WARNING,
            extra={
                "op": "reject_match",
                "listing_id": str(listing_id),
                "product_sku": product_sku,
            },
        )
        return None

    async def get_stats(self) -> ComparisonStats:
        logger.warning(DISABLED_WARNING, extra={"op": "get_stats"})
        return ComparisonStats(
            listings_total=0,
            listings_with_match=0,
            decisions_pending=0,
            decisions_confirmed=0,
            decisions_rejected=0,
        )


__all__ = ["DISABLED_WARNING", "NoopComparatorService"]
