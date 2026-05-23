"""RisFactory — devuelve adapter ReverseImageSearchPort activo (US-F15-02-03).

Lógica de resolución:
1. Flag ``reverse_image_search`` OFF → NoopRisAdapter.
2. REVERSE_IMAGE_DAILY_LIMIT == 0 → NoopRisAdapter.
3. REVERSE_IMAGE_PROVIDER=tineye + TINEYE_API_KEY → TinEyeAdapter.
4. REVERSE_IMAGE_PROVIDER=google_lens_serpapi + SERPAPI_KEY → GoogleLensSerpApiAdapter.
5. Si redis inyectado → envolver en RateLimitedRisAdapter.

Patrón mirror de VlmJudgeFactory (app/services/comparator/factory.py).
"""

from __future__ import annotations

import logging

from app.services.comparator.interfaces import ReverseImageSearchPort
from app.services.image_search.ris_adapters import (
    GoogleLensSerpApiAdapter,
    NoopRisAdapter,
    RateLimitedRisAdapter,
    TinEyeAdapter,
)
from app.services.image_search.ris_limit import RedisLike

logger = logging.getLogger(__name__)

_FLAG_RIS = "reverse_image_search"


class RisFactory:
    """Factory síncrona — devuelve adapter ReverseImageSearchPort activo."""

    @staticmethod
    def create(redis: RedisLike | None = None) -> ReverseImageSearchPort:
        if not RisFactory._is_flag_enabled():
            return NoopRisAdapter()

        try:
            from app.core.config import get_settings

            settings = get_settings()
        except Exception as exc:  # noqa: BLE001
            logger.warning("ris.factory: settings import failed: %s", exc)
            return NoopRisAdapter()

        if not settings.REVERSE_IMAGE_DAILY_LIMIT:
            return NoopRisAdapter()

        provider = settings.REVERSE_IMAGE_PROVIDER
        if provider == "tineye":
            api_key = settings.TINEYE_API_KEY.get_secret_value()
            if not api_key:
                logger.warning(
                    "ris.factory: REVERSE_IMAGE_PROVIDER=tineye pero "
                    "TINEYE_API_KEY vacío — NoopRisAdapter"
                )
                return NoopRisAdapter()
            inner: ReverseImageSearchPort = TinEyeAdapter(api_key=api_key)
        elif provider == "google_lens_serpapi":
            api_key = settings.SERPAPI_KEY.get_secret_value()
            if not api_key:
                logger.warning(
                    "ris.factory: REVERSE_IMAGE_PROVIDER=google_lens_serpapi pero "
                    "SERPAPI_KEY vacío — NoopRisAdapter"
                )
                return NoopRisAdapter()
            inner = GoogleLensSerpApiAdapter(api_key=api_key)
        else:
            logger.warning(
                "ris.factory: REVERSE_IMAGE_PROVIDER=%r desconocido — NoopRisAdapter",
                provider,
            )
            return NoopRisAdapter()

        if redis is not None:
            return RateLimitedRisAdapter(
                inner, redis=redis, limit=settings.REVERSE_IMAGE_DAILY_LIMIT
            )
        return inner

    @staticmethod
    def _is_flag_enabled() -> bool:
        try:
            from app.services.feature_flags.flag_service import (
                FLAG_REVERSE_IMAGE_SEARCH,
                is_enabled as flag_is_enabled,
            )
        except Exception as exc:  # noqa: BLE001
            logger.warning("ris.factory: flag_service import failed: %s", exc)
            return False
        return flag_is_enabled(FLAG_REVERSE_IMAGE_SEARCH)


__all__ = ["RisFactory"]
