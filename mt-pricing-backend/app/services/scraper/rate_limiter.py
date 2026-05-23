"""Token bucket rate limiter por dominio usando Redis (US-SCR-03-03).

Algoritmo:
- Bucket por dominio en Redis key ``rate_limit:{domain}``
- Cada key contiene el número de tokens disponibles
- ``acquire()`` decrementa atómicamente usando EVAL Lua
- Si no hay tokens: espera hasta que se repongan (backoff)
- Los tokens se reponen via TTL automático cada ventana (60s por defecto)

Integración:
- Usado en ``scrape_brand_task`` + ``price_monitor_task`` antes de cada request HTTP.
- Config via ``settings.SCRAPER_RATE_LIMIT_RPM`` (default: 20 req/min).
"""

from __future__ import annotations

import asyncio
import logging
import random
import time

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lua script — adquiere 1 token del bucket de forma atómica
# ---------------------------------------------------------------------------

_ACQUIRE_SCRIPT = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local window_seconds = tonumber(ARGV[2])

local current = tonumber(redis.call('GET', key) or capacity)
if current <= 0 then
    return 0  -- no hay tokens
end

local new_val = current - 1
redis.call('SET', key, new_val, 'EX', window_seconds)
return 1  -- token adquirido
"""

# ---------------------------------------------------------------------------
# User-Agent pool
# ---------------------------------------------------------------------------

_DEFAULT_UA_POOL: list[str] = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14.4; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36 Edg/124.0.0.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_4 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Mobile/15E148 Safari/604.1",
]

_ACCEPT_LANGUAGE_POOL: list[str] = [
    "en-US,en;q=0.9",
    "en-GB,en;q=0.9",
    "en-AE,en;q=0.9,ar;q=0.8",
    "en-US,en;q=0.9,ar;q=0.8",
    "ar-AE,ar;q=0.9,en;q=0.8",
    "en-US,en;q=0.9,fr;q=0.8",
]


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------


class RateLimiter:
    """Token bucket rate limiter usando Redis.

    Args:
        redis_url: URL de Redis (e.g. ``redis://redis:6379/0``).
        rpm: Requests por minuto permitidos por dominio.
        window_seconds: Ventana de tiempo (default: 60s).
        ua_pool: Pool de User-Agent strings. None = usar pool por defecto.
    """

    def __init__(
        self,
        redis_url: str,
        *,
        rpm: int = 5,
        window_seconds: int = 60,
        ua_pool: list[str] | None = None,
    ) -> None:
        self._redis_url = redis_url
        self._rpm = rpm
        self._window_seconds = window_seconds
        self._ua_pool = ua_pool or _DEFAULT_UA_POOL
        self._redis: aioredis.Redis | None = None
        self._script_sha: str | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def _load_script(self, r: aioredis.Redis) -> str:
        if self._script_sha is None:
            self._script_sha = await r.script_load(_ACQUIRE_SCRIPT)
        return self._script_sha

    async def acquire(self, domain: str, *, max_wait_seconds: float = 60.0) -> bool:
        """Adquiere un token para el dominio dado.

        Espera hasta ``max_wait_seconds`` si el bucket está vacío.
        Returns True cuando el token fue adquirido, False si se agotó el tiempo.
        """
        key = f"rate_limit:{domain}"
        deadline = time.monotonic() + max_wait_seconds

        try:
            r = await self._get_redis()
            sha = await self._load_script(r)

            while time.monotonic() < deadline:
                result = await r.evalsha(  # type: ignore[attr-defined]
                    sha,
                    1,
                    key,
                    str(self._rpm),
                    str(self._window_seconds),
                )
                if result == 1:
                    logger.debug(
                        "rate_limiter.token_acquired",
                        extra={"domain": domain, "rpm": self._rpm},
                    )
                    return True

                # No hay tokens — esperar una fracción de la ventana
                wait = self._window_seconds / self._rpm
                jitter = random.uniform(0.0, wait * 0.2)
                logger.debug(
                    "rate_limiter.throttled",
                    extra={"domain": domain, "wait_s": round(wait + jitter, 2)},
                )
                await asyncio.sleep(wait + jitter)

        except Exception as exc:
            # Si Redis falla, permitir el request (fail-open)
            logger.warning(
                "rate_limiter.redis_error",
                extra={"domain": domain, "error": str(exc)[:120]},
            )
            return True

        logger.warning(
            "rate_limiter.timeout",
            extra={"domain": domain, "max_wait_s": max_wait_seconds},
        )
        return False

    def get_headers(self) -> dict[str, str]:
        """Devuelve headers HTTP con User-Agent y Accept-Language rotados aleatoriamente."""
        ua = random.choice(self._ua_pool)
        accept_lang = random.choice(_ACCEPT_LANGUAGE_POOL)
        return {
            "User-Agent": ua,
            "Accept-Language": accept_lang,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
        }

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


# ---------------------------------------------------------------------------
# Singleton lazy (para tasks Celery — se inicializa en el primer uso)
# ---------------------------------------------------------------------------

_rate_limiter_instance: RateLimiter | None = None


def get_rate_limiter() -> RateLimiter:
    """Devuelve la instancia singleton del RateLimiter.

    Inicializa desde ``app.core.config.settings`` en el primer uso.
    """
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        from app.core.config import settings

        ua_pool_raw = getattr(settings, "SCRAPER_UA_POOL", None)
        ua_pool: list[str] | None = None
        if ua_pool_raw:
            ua_pool = [ua.strip() for ua in ua_pool_raw.split("||") if ua.strip()]

        _rate_limiter_instance = RateLimiter(
            redis_url=str(settings.REDIS_URL),
            rpm=getattr(settings, "SCRAPER_RATE_LIMIT_RPM", 5),
            ua_pool=ua_pool,
        )
    return _rate_limiter_instance
