"""ComparatorServiceFactory — devuelve stub o real según flag (ADR-012).

Fase 1: flag ``COMPARATOR_ENABLED`` se siembra a ``false`` (mig. 069). Mientras
el flag esté OFF el factory devuelve :class:`NoopComparatorService`. La
implementación real se enchufa en Fase 1.5+ sin tocar callers — basta
flip del flag + registro de la nueva clase aquí.

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

        Fase 1: siempre :class:`NoopComparatorService` (el flag está OFF y
        la implementación real no existe todavía).

        Fase 1.5+: cuando el research workstream entregue, registrar aquí
        ``ProductComparisonService(...)`` y devolverlo si el flag está ON.
        """
        if ComparatorServiceFactory._is_enabled():
            # Fase 1.5+: cuando exista ProductComparisonService, importar y
            # construir aquí. Por ahora, aún con flag ON, no hay
            # implementación real → fallback seguro al stub.
            logger.warning(
                "comparator: flag COMPARATOR_ENABLED=ON pero la "
                "implementación real aún no está disponible; "
                "usando NoopComparatorService"
            )
            return NoopComparatorService()
        return NoopComparatorService()

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


__all__ = ["FLAG_COMPARATOR_ENABLED", "ComparatorServiceFactory"]
