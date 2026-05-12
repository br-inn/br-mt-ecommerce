"""ComparatorServiceFactory — devuelve adapter según flag + COMPARATOR_ADAPTER.

Lógica de resolución (US-RND-01-11 / FR-CMP-GRAPH-01):

1. Si ``COMPARATOR_ENABLED`` está OFF (default Fase 1) → :class:`NoopComparatorService`.
2. Si está ON, leer ``settings.COMPARATOR_ADAPTER``:
   - ``rag_only``       → :class:`RagOnlyComparatorAdapter` (Fase 1 activo).
   - ``hybrid``         → :class:`HybridComparatorAdapter` (stub Fase 2).
   - ``full_graph_rag`` → :class:`FullGraphRagComparatorAdapter` (stub Fase 2+).

Swap sin tocar endpoints de API — sólo env var + flag flip.

Patrón mirror de :mod:`app.services.feature_flags.flag_service` (lookup
síncrono via cache local in-process). Si no hay flag service bootstrappeado
(e.g. tests sin DI), se devuelve el stub: modo seguro.
"""

from __future__ import annotations

import logging

from app.services.comparator.interfaces import ComparatorPort
from app.services.comparator.noop_service import NoopComparatorService

logger = logging.getLogger(__name__)


# Flag canónico — añadir a flag_service.KNOWN_FLAGS para que el endpoint
# admin/flags lo exponga.
FLAG_COMPARATOR_ENABLED = "COMPARATOR_ENABLED"


class ComparatorServiceFactory:
    """Factory síncrona — resuelve la instancia ``ComparatorPort`` a usar."""

    @staticmethod
    def create() -> ComparatorPort:
        """Devuelve la implementación activa.

        Fase 1 (default):
          - Flag OFF → :class:`NoopComparatorService`.
          - Flag ON + ``COMPARATOR_ADAPTER=rag_only`` → :class:`RagOnlyComparatorAdapter`.

        Fase 2+ (stub disponibles pero no activos):
          - ``COMPARATOR_ADAPTER=hybrid`` → :class:`HybridComparatorAdapter`.
          - ``COMPARATOR_ADAPTER=full_graph_rag`` → :class:`FullGraphRagComparatorAdapter`.
        """
        if not ComparatorServiceFactory._is_enabled():
            return NoopComparatorService()

        adapter_name = ComparatorServiceFactory._get_adapter_name()
        return ComparatorServiceFactory._build_adapter(adapter_name)

    @staticmethod
    def _is_enabled() -> bool:
        """Lookup síncrono del flag — import diferido para evitar ciclos."""
        try:
            from app.services.feature_flags.flag_service import (
                is_enabled as flag_is_enabled,
            )
        except Exception:  # noqa: BLE001 — feature_flags opcional en tests
            return False
        return flag_is_enabled(FLAG_COMPARATOR_ENABLED)

    @staticmethod
    def _get_adapter_name() -> str:
        """Lee ``settings.COMPARATOR_ADAPTER`` (default ``rag_only``)."""
        try:
            from app.core.config import settings

            return settings.COMPARATOR_ADAPTER
        except Exception:  # noqa: BLE001 — config opcional en tests
            return "rag_only"

    @staticmethod
    def _build_adapter(adapter_name: str) -> ComparatorPort:
        """Construye el adapter según el nombre.

        Importación diferida para evitar ciclos y reducir overhead de import
        cuando el factory siempre devuelve Noop (flag OFF, default Fase 1).
        """
        from app.services.comparator.adapters import (
            FullGraphRagComparatorAdapter,
            HybridComparatorAdapter,
            RagOnlyComparatorAdapter,
        )

        if adapter_name == "rag_only":
            return RagOnlyComparatorAdapter()
        if adapter_name == "hybrid":
            logger.info(
                "comparator.factory: adapter=hybrid (stub Fase 2 — "
                "métodos lanzan NotImplementedError)"
            )
            return HybridComparatorAdapter()
        if adapter_name == "full_graph_rag":
            logger.info(
                "comparator.factory: adapter=full_graph_rag (stub Fase 2+ — "
                "métodos lanzan NotImplementedError)"
            )
            return FullGraphRagComparatorAdapter()

        # Valor desconocido — fallback seguro + warning
        logger.warning(
            "comparator.factory: COMPARATOR_ADAPTER=%r desconocido; "
            "usando rag_only como fallback",
            adapter_name,
        )
        return RagOnlyComparatorAdapter()


__all__ = ["FLAG_COMPARATOR_ENABLED", "ComparatorServiceFactory"]
