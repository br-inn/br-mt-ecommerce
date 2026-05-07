"""Registry/factory para los fetchers de matching (Sprint 4 scaffold).

Decide entre el stub Sprint 3 (canned, sin red) y el adapter real S4
(httpx + retry + circuit breaker) leyendo el flag de entorno
``MT_LIVE_NETWORK``.

Defaults a ``False`` — modo seguro por defecto. Cuando se activa
``MT_LIVE_NETWORK=true`` la fábrica retorna el adapter real, que
internamente sigue cayendo al stub si las credenciales no están
configuradas (defensa en profundidad).

Uso::

    from app.services.matching.adapter_registry import get_fetcher

    fetcher = get_fetcher("amazon_uae")
    candidates = await fetcher.fetch(query, sku=sku)

Ports: :class:`app.services.matching.ports.FetcherPort`.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.matching.ports import FetcherPort


_LIVE_ENV = "MT_LIVE_NETWORK"


def _live_network_enabled() -> bool:
    """True solo si ``MT_LIVE_NETWORK`` ∈ {1, true, yes, on} (case-insensitive)."""
    val = os.environ.get(_LIVE_ENV, "false").strip().lower()
    return val in {"1", "true", "yes", "on"}


def get_fetcher(channel: str) -> FetcherPort:
    """Devuelve el fetcher adecuado para un canal.

    Args:
        channel: ``amazon_uae`` o ``noon_uae``.

    Raises:
        ValueError: canal desconocido.
    """
    if channel == "amazon_uae":
        if _live_network_enabled():
            from app.services.matching.adapters.bright_data_amazon_uae import (
                BrightDataAmazonUaeFetcher,
            )

            return BrightDataAmazonUaeFetcher()
        from app.services.matching.adapters.amazon_uae_stub import AmazonUaeStubFetcher

        return AmazonUaeStubFetcher()

    if channel == "noon_uae":
        if _live_network_enabled():
            from app.services.matching.adapters.playwright_noon_uae import (
                PlaywrightNoonUaeFetcher,
            )

            return PlaywrightNoonUaeFetcher()
        from app.services.matching.adapters.noon_uae_stub import NoonUaeStubFetcher

        return NoonUaeStubFetcher()

    raise ValueError(f"Unknown matching channel: {channel!r}")


__all__ = ["get_fetcher"]
