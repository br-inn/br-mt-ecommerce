"""Adapters concretos del :class:`FetcherPort`.

Sprint 3 — sólo stubs canned (sin red). Cuando entren Bright Data /
Playwright se añaden módulos hermanos sin tocar el orquestador.
"""

from __future__ import annotations

from app.services.matching.adapters.amazon_uae_stub import AmazonUaeStubFetcher
from app.services.matching.adapters.noon_uae_stub import NoonUaeStubFetcher

__all__ = ["AmazonUaeStubFetcher", "NoonUaeStubFetcher"]
