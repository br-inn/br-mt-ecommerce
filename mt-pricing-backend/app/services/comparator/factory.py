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

from app.services.comparator.interfaces import ComparatorPort, VlmJudgePort
from app.services.comparator.noop_service import NoopComparatorService

logger = logging.getLogger(__name__)


FLAG_COMPARATOR_ENABLED = "COMPARATOR_ENABLED"
FLAG_VLM_JUDGE_ENABLED = "VLM_JUDGE_ENABLED"


class ComparatorServiceFactory:
    """Factory síncrona — resuelve la instancia ``ComparatorPort`` a usar."""

    @staticmethod
    def create() -> ComparatorPort:
        """Devuelve la implementación activa.

        Fase 1 (default):
          - Flag OFF → :class:`NoopComparatorService`.
          - Flag ON + ``COMPARATOR_ADAPTER=rag_only`` → :class:`RagOnlyComparatorAdapter`.

        Fase 2+ (no disponibles en Fase 1):
          - ``COMPARATOR_ADAPTER=hybrid`` o ``full_graph_rag`` → :exc:`ValueError`
            al arrancar; estos adapters sólo se activan en Fase 2+.
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
        except Exception as exc:  # noqa: BLE001 — feature_flags opcional en tests
            logger.warning("comparator.factory: flag_service import failed: %s", exc)
            return False
        return flag_is_enabled(FLAG_COMPARATOR_ENABLED)

    @staticmethod
    def _get_adapter_name() -> str:
        """Lee ``settings.COMPARATOR_ADAPTER`` (default ``rag_only``)."""
        try:
            from app.core.config import settings

            return settings.COMPARATOR_ADAPTER
        except Exception as exc:  # noqa: BLE001 — config opcional en tests
            logger.warning("comparator.factory: settings import failed: %s", exc)
            return "rag_only"

    @staticmethod
    def _build_adapter(adapter_name: str) -> ComparatorPort:
        """Construye el adapter según el nombre.

        Importación diferida para evitar ciclos y reducir overhead de import
        cuando el factory siempre devuelve Noop (flag OFF, default Fase 1).

        Raises:
            ValueError: si ``adapter_name`` es ``hybrid`` o ``full_graph_rag``
                (no disponibles en Fase 1 — activar en Fase 2+).
        """
        # FD-1: adapters Fase 2+ causan error al arrancar para evitar crashes
        # silenciosos en runtime (todos sus métodos lanzan NotImplementedError).
        if adapter_name in ("hybrid", "full_graph_rag"):
            raise ValueError(
                f"COMPARATOR_ADAPTER={adapter_name!r} no está disponible en Fase 1. "
                "Sólo 'rag_only' está activo. Activar Hybrid/FullGraphRag en Fase 2+."
            )

        from app.services.comparator.adapters import RagOnlyComparatorAdapter

        if adapter_name == "rag_only":
            return RagOnlyComparatorAdapter()

        # Valor desconocido — fallback seguro + warning
        logger.warning(
            "comparator.factory: COMPARATOR_ADAPTER=%r desconocido; usando rag_only como fallback",
            adapter_name,
        )
        return RagOnlyComparatorAdapter()


class VlmJudgeFactory:
    """Factory síncrona — devuelve adapter VlmJudgePort activo.

    Fase 1.5+: VLM_JUDGE_ENABLED=true + ANTHROPIC_API_KEY → ClaudeVlmJudgeAdapter.
    Default: NoopVlmJudgeAdapter (safe default).
    """

    @staticmethod
    def create() -> VlmJudgePort:
        if not VlmJudgeFactory._is_enabled():
            from app.services.comparator.vlm_judge_stub import NoopVlmJudgeAdapter

            return NoopVlmJudgeAdapter()

        api_key = VlmJudgeFactory._get_api_key()
        if not api_key:
            logger.warning(
                "comparator.vlm_judge_factory: VLM_JUDGE_ENABLED=true pero "
                "ANTHROPIC_API_KEY vacío — usando NoopVlmJudgeAdapter"
            )
            from app.services.comparator.vlm_judge_stub import NoopVlmJudgeAdapter

            return NoopVlmJudgeAdapter()

        from app.services.comparator.vlm_judge_adapter import ClaudeVlmJudgeAdapter

        try:
            from app.core.config import settings as _s

            redis_url = str(_s.REDIS_URL)
            allowed_domains = frozenset(_s.VLM_ALLOWED_IMAGE_DOMAINS)
        except Exception as exc:  # noqa: BLE001
            logger.warning("comparator.vlm_judge_factory: settings import failed: %s", exc)
            redis_url = None
            allowed_domains = frozenset()

        return ClaudeVlmJudgeAdapter(
            api_key=api_key,
            redis_url=redis_url,
            allowed_image_domains=allowed_domains,
        )

    @staticmethod
    def _is_enabled() -> bool:
        try:
            from app.services.feature_flags.flag_service import (
                is_enabled as flag_is_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("comparator.vlm_judge_factory: flag_service import failed: %s", exc)
            return False
        return flag_is_enabled(FLAG_VLM_JUDGE_ENABLED)

    @staticmethod
    def _get_api_key() -> str:
        try:
            from app.core.config import settings

            return settings.ANTHROPIC_API_KEY.get_secret_value()
        except Exception as exc:  # noqa: BLE001
            logger.warning("comparator.vlm_judge_factory: settings import failed: %s", exc)
            return ""


__all__ = [
    "FLAG_COMPARATOR_ENABLED",
    "FLAG_VLM_JUDGE_ENABLED",
    "ComparatorServiceFactory",
    "VlmJudgeFactory",
]
