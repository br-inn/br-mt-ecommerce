"""Registry/factory para los fetchers de matching.

Selecciona el adapter real según feature flags. Si ningún flag está activo
o el scraper es bloqueado, devuelve lista vacía (sin stubs ni datos falsos).

Kill-switch global → siempre vacío.
"""

from __future__ import annotations

import os
from typing import TYPE_CHECKING

from app.services.feature_flags.flag_service import (
    FLAG_LIVE_NETWORK_NOON_UAE,
    FLAG_PATCHRIGHT_SCRAPER_AMAZON_UAE as _FLAG_PATCHRIGHT,
    get_default_service,
    is_enabled,
)
from app.services.feature_flags.kill_switch import is_kill_switch_engaged

if TYPE_CHECKING:
    from app.services.matching.ports import CandidateRaw, FetcherPort, Query


_LIVE_ENV = "MT_LIVE_NETWORK"

# Tier 1 scraper flag — activates CurlCffiAmazonUaeFetcher.
# Set to True in feature_flags table (or via warmup_local_cache in tests) to enable.
FLAG_LIVE_SCRAPER_AMAZON_UAE = "live_scraper_amazon_uae"

# Tier 2 scraper flag — activates PatchrightAmazonUaeFetcher.
# Requires the mt-scraper-worker container to be running (see Dockerfile.scraper-worker).
FLAG_PATCHRIGHT_SCRAPER_AMAZON_UAE = _FLAG_PATCHRIGHT


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


class _EmptyFetcher:
    """Fetcher nulo — devuelve lista vacía sin tocar la red ni generar datos falsos."""

    def __init__(self, channel: str) -> None:
        self.channel = channel

    async def fetch(self, query: "Query", *, sku: str | None = None) -> "list[CandidateRaw]":
        return []


class _BlockFallbackWrapper:
    """Envuelve un fetcher real; devuelve el fallback si es bloqueado."""

    def __init__(self, primary: "FetcherPort", fallback: "FetcherPort") -> None:
        self._primary = primary
        self._fallback = fallback

    @property
    def channel(self) -> str:
        return self._primary.channel  # type: ignore[attr-defined]

    async def fetch(self, query: "Query", *, sku: str | None = None) -> "list[CandidateRaw]":
        from app.services.matching.scraper_errors import ScraperBlockedError
        import logging

        try:
            return await self._primary.fetch(query, sku=sku)
        except ScraperBlockedError as exc:
            logging.getLogger(__name__).warning(
                "scraper.blocked",
                extra={"channel": self.channel, "error": str(exc)[:120]},
            )
            return await self._fallback.fetch(query, sku=sku)


def _get_amazon_uae_fetcher() -> "FetcherPort":
    """Prioridad: curl_cffi → patchright → vacío (nunca stubs)."""
    import logging
    log = logging.getLogger(__name__)
    empty = _EmptyFetcher("amazon_uae")

    curl_active = _live_for(FLAG_LIVE_SCRAPER_AMAZON_UAE)
    patchright_active = _live_for(FLAG_PATCHRIGHT_SCRAPER_AMAZON_UAE)

    if curl_active:
        try:
            from app.services.matching.adapters.curl_cffi_amazon_uae import CurlCffiAmazonUaeFetcher
        except ImportError:
            log.warning("curl_cffi no disponible en este contenedor — amazon_uae desactivado")
            return empty

        fallback: "FetcherPort"
        if patchright_active:
            try:
                from app.services.matching.adapters.patchright_amazon_uae import PatchrightAmazonUaeFetcher
                fallback = _BlockFallbackWrapper(PatchrightAmazonUaeFetcher(), empty)
            except ImportError:
                fallback = empty
        else:
            fallback = empty

        return _BlockFallbackWrapper(CurlCffiAmazonUaeFetcher(), fallback)

    if patchright_active:
        try:
            from app.services.matching.adapters.patchright_amazon_uae import PatchrightAmazonUaeFetcher
        except ImportError:
            log.warning("patchright no disponible en este contenedor — amazon_uae desactivado")
            return empty
        return _BlockFallbackWrapper(PatchrightAmazonUaeFetcher(), empty)

    return empty


def get_fetcher(channel: str) -> "FetcherPort":
    """Devuelve el fetcher adecuado para un canal.

    Args:
        channel: ``amazon_uae`` o ``noon_uae``.

    Raises:
        ValueError: canal desconocido.
    """
    if channel == "amazon_uae":
        return _get_amazon_uae_fetcher()

    if channel == "noon_uae":
        if _live_for(FLAG_LIVE_NETWORK_NOON_UAE):
            from app.services.matching.adapters.playwright_noon_uae import (
                PlaywrightNoonUaeFetcher,
            )

            return PlaywrightNoonUaeFetcher()
        return _EmptyFetcher("noon_uae")

    raise ValueError(f"Unknown matching channel: {channel!r}")


__all__ = [
    "FLAG_LIVE_SCRAPER_AMAZON_UAE",
    "FLAG_PATCHRIGHT_SCRAPER_AMAZON_UAE",
    "get_fetcher",
]
