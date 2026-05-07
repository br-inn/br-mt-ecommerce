"""Async Redis client — singleton cacheado.

Usos:
- Cache aplicativo (TTLs cortos, keys con prefijo `mt:cache:*`).
- Heartbeats custom de workers Celery (ADR-048 §healthchecks).
- Locks distribuidos (importer dedupe, scheduler leader election).
"""

from __future__ import annotations

from functools import lru_cache

from redis.asyncio import Redis, from_url

from app.core.config import settings


@lru_cache(maxsize=1)
def get_redis() -> Redis:
    """Cliente async — connection pool implícito en `redis.asyncio`."""
    return from_url(
        str(settings.REDIS_URL),
        encoding="utf-8",
        decode_responses=True,
        socket_timeout=5,
        socket_connect_timeout=2,
        health_check_interval=30,
    )


async def close_redis() -> None:
    """Llamar en lifespan shutdown para cerrar conexiones cleanly."""
    client = get_redis()
    await client.aclose()
