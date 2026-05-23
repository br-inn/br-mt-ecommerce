"""Adapters de Reverse Image Search — US-F15-02-03.

Implementaciones de ReverseImageSearchPort:
- NoopRisAdapter      — safe default cuando flag OFF o sin API key.
- TinEyeAdapter       — TinEye JSON API v1.1 via httpx.
- GoogleLensSerpApiAdapter — SerpAPI Google Lens via httpx.
- RateLimitedRisAdapter   — wrapper que aplica daily limit via Redis INCR.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from urllib.parse import urlparse

import httpx

from app.services.comparator.interfaces import (
    ReverseImageHit,
    ReverseImageSearchPort,
    ReverseImageSearchResult,
)
from app.services.image_search.ris_limit import RedisLike, check_and_increment

logger = logging.getLogger(__name__)

_TINEYE_API_BASE = "https://api.tineye.com/rest/search/"
_SERPAPI_BASE = "https://serpapi.com/search"


class NoopRisAdapter(ReverseImageSearchPort):
    """Retorna hits vacíos sin llamadas externas — usado cuando flag OFF."""

    async def search(self, *, image_url: str, max_results: int = 10) -> ReverseImageSearchResult:
        return ReverseImageSearchResult(
            provider="noop",
            hits=(),
            searched_at=datetime.now(tz=UTC),
        )


class TinEyeAdapter(ReverseImageSearchPort):
    """Llama a TinEye JSON API v1.1 con httpx."""

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, *, image_url: str, max_results: int = 10) -> ReverseImageSearchResult:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    _TINEYE_API_BASE,
                    params={
                        "image_url": image_url,
                        "limit": max_results,
                        "api_key": self._api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            matches = (data.get("results") or {}).get("matches") or []
            hits = tuple(
                ReverseImageHit(
                    url=m.get("image_url", ""),
                    domain=(m.get("domain") or urlparse(m.get("image_url", "")).netloc),
                    similarity=float(m.get("score", 0.0)),
                )
                for m in matches
            )
            return ReverseImageSearchResult(
                provider="tineye",
                hits=hits,
                searched_at=datetime.now(tz=UTC),
            )
        except Exception as exc:
            logger.warning("ris.tineye.search failed image_url=%s: %s", image_url, exc)
            return ReverseImageSearchResult(
                provider="tineye_error",
                hits=(),
                searched_at=datetime.now(tz=UTC),
            )


class GoogleLensSerpApiAdapter(ReverseImageSearchPort):
    """Llama a SerpAPI Google Lens con httpx."""

    def __init__(self, *, api_key: str) -> None:
        self._api_key = api_key

    async def search(self, *, image_url: str, max_results: int = 10) -> ReverseImageSearchResult:
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(
                    _SERPAPI_BASE,
                    params={
                        "engine": "google_lens",
                        "url": image_url,
                        "api_key": self._api_key,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            matches = (data.get("visual_matches") or [])[:max_results]
            hits = tuple(
                ReverseImageHit(
                    url=m.get("link", ""),
                    domain=(m.get("source", "") or urlparse(m.get("link", "")).netloc),
                    similarity=0.0,
                    thumbnail_url=m.get("thumbnail"),
                )
                for m in matches
            )
            return ReverseImageSearchResult(
                provider="google_lens_serpapi",
                hits=hits,
                searched_at=datetime.now(tz=UTC),
            )
        except Exception as exc:
            logger.warning("ris.google_lens.search failed image_url=%s: %s", image_url, exc)
            return ReverseImageSearchResult(
                provider="google_lens_error",
                hits=(),
                searched_at=datetime.now(tz=UTC),
            )


class RateLimitedRisAdapter(ReverseImageSearchPort):
    """Envuelve un adapter real y aplica daily limit via Redis INCR."""

    def __init__(
        self,
        inner: ReverseImageSearchPort,
        *,
        redis: RedisLike,
        limit: int,
    ) -> None:
        self._inner = inner
        self._redis = redis
        self._limit = limit

    async def search(self, *, image_url: str, max_results: int = 10) -> ReverseImageSearchResult:
        allowed = await check_and_increment(self._redis, limit=self._limit)
        if not allowed:
            return ReverseImageSearchResult(
                provider="limit_reached",
                hits=(),
                searched_at=datetime.now(tz=UTC),
            )
        return await self._inner.search(image_url=image_url, max_results=max_results)


__all__ = [
    "GoogleLensSerpApiAdapter",
    "NoopRisAdapter",
    "RateLimitedRisAdapter",
    "TinEyeAdapter",
]
