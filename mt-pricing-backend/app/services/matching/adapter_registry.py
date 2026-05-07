"""Registry/factory para los fetchers de matching (Sprint 4 → Sprint 5).

Decide entre el stub Sprint 3 (canned, sin red) y el adapter real S4
(httpx + retry + circuit breaker). En Sprint 5 (US-1A-09-08) la fuente de
verdad pasa de la env var ``MT_LIVE_NETWORK`` a flags por canal en la tabla
``feature_flags``, leídos vía :mod:`app.services.feature_flags.flag_service`.

Defaults a ``False`` — modo seguro por defecto (sin servicio bootstrappeado).
El kill-switch global (:func:`is_kill_switch_engaged`) overridea todos los
flags de canal: si está engaged, el factory devuelve siempre stubs.

Backwards-compat: si no hay :class:`FlagService` bootstrappeado (e.g. tests
del registry, dev sin DB), seguimos respetando ``MT_LIVE_NETWORK`` env var
como atajo (degraded mode).

Uso::

    from app.services.matching.adapter_registry import get_fetcher

    fetcher = get_fetcher("amazon_uae")
    candidates = await fetcher.fetch(query, sku=sku)

Ports: :class:`app.services.matching.ports.FetcherPort`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.services.feature_flags.flag_service import (
    FLAG_LIVE_NETWORK_AMAZON_UAE,
    FLAG_LIVE_NETWORK_NOON_UAE,
    get_default_service,
    is_enabled,
)
from app.services.feature_flags.kill_switch import is_kill_switch_engaged

if TYPE_CHECKING:
    from app.services.matching.ports import FetcherPort


_LIVE_ENV = "MT_LIVE_NETWORK"


def _env_fallback_enabled() -> bool:
    """Fallback legacy — sólo se aplica si NO hay FlagService bootstrappeado."""
    val = os.environ.get(_LIVE_ENV, "false").strip().lower()
    return val in {"1", "true", "yes", "on"}


def _live_for(flag_key: str) -> bool:
    """Resuelve el toggle final (flag service > env var) con kill-switch global."""
    if is_kill_switch_engaged():
        return False
    if get_default_service() is not None:
        return is_enabled(flag_key)
    return _env_fallback_enabled()


def get_fetcher(channel: str) -> FetcherPort:
    """Devuelve el fetcher adecuado para un canal.

    Args:
        channel: ``amazon_uae`` o ``noon_uae``.

    Raises:
        ValueError: canal desconocido.
    """
    if channel == "amazon_uae":
        if _live_for(FLAG_LIVE_NETWORK_AMAZON_UAE):
            from app.services.matching.adapters.bright_data_amazon_uae import (
                BrightDataAmazonUaeFetcher,
            )

            return BrightDataAmazonUaeFetcher()
        from app.services.matching.adapters.amazon_uae_stub import AmazonUaeStubFetcher

        return AmazonUaeStubFetcher()

    if channel == "noon_uae":
        if _live_for(FLAG_LIVE_NETWORK_NOON_UAE):
            from app.services.matching.adapters.playwright_noon_uae import (
                PlaywrightNoonUaeFetcher,
            )

            return PlaywrightNoonUaeFetcher()
        from app.services.matching.adapters.noon_uae_stub import NoonUaeStubFetcher

        return NoonUaeStubFetcher()

    raise ValueError(f"Unknown matching channel: {channel!r}")


__all__ = ["get_fetcher"]
