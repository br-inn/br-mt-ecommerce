"""Circuit breaker per-domain con proxy pool distribuido Redis (US-SCR-03-04).

Estados del circuit breaker:
- CLOSED: operación normal. Contabiliza fallos.
- OPEN: dominio bloqueado (demasiados fallos). Retorna ScraperCircuitOpenError.
- HALF_OPEN: prueba de recuperación. Un request de prueba.

Almacenamiento Redis:
- ``circuit:{domain}:state``  → "closed" | "open" | "half_open"
- ``circuit:{domain}:failures`` → contador de fallos en ventana
- ``circuit:{domain}:opened_at`` → timestamp UNIX cuando se abrió
- ``proxy_pool`` → lista de proxies (LPUSH para añadir, RPOP para consumir)

Config:
- ``SCRAPER_CB_FAILURE_THRESHOLD`` (default: 5) — fallos antes de OPEN
- ``SCRAPER_CB_RECOVERY_TIMEOUT`` (default: 60) — segundos en OPEN antes de HALF_OPEN
"""

from __future__ import annotations

import logging
import time
from enum import Enum

import redis.asyncio as aioredis

logger = logging.getLogger(__name__)

PROXY_POOL_KEY = "proxy_pool"


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class ScraperCircuitOpenError(Exception):
    """Lanzada cuando el circuit breaker está abierto para un dominio."""

    def __init__(self, domain: str) -> None:
        super().__init__(f"Circuit breaker OPEN for domain: {domain}")
        self.domain = domain


class CircuitBreaker:
    """Circuit breaker per-domain con estado en Redis.

    Args:
        redis_url: URL Redis.
        failure_threshold: Fallos consecutivos antes de OPEN (default: 5).
        recovery_timeout: Segundos en OPEN antes de HALF_OPEN (default: 60).
        failure_window: Ventana TTL del contador de fallos en segundos (default: 120).
    """

    def __init__(
        self,
        redis_url: str,
        *,
        failure_threshold: int = 5,
        recovery_timeout: int = 60,
        failure_window: int = 120,
    ) -> None:
        self._redis_url = redis_url
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._failure_window = failure_window
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    def _keys(self, domain: str) -> tuple[str, str, str]:
        return (
            f"circuit:{domain}:state",
            f"circuit:{domain}:failures",
            f"circuit:{domain}:opened_at",
        )

    async def get_state(self, domain: str) -> CircuitState:
        """Retorna el estado actual del circuit para el dominio."""
        try:
            r = await self._get_redis()
            state_key, _, opened_at_key = self._keys(domain)

            state_raw = await r.get(state_key)
            if state_raw is None:
                return CircuitState.CLOSED

            state = CircuitState(state_raw)

            # Si está OPEN, verificar si ya pasó el recovery timeout
            if state == CircuitState.OPEN:
                opened_at_raw = await r.get(opened_at_key)
                if opened_at_raw:
                    elapsed = time.time() - float(opened_at_raw)
                    if elapsed >= self._recovery_timeout:
                        await r.set(state_key, CircuitState.HALF_OPEN, ex=self._failure_window * 2)
                        logger.info(
                            "circuit_breaker.half_open",
                            extra={"domain": domain, "elapsed_s": round(elapsed, 1)},
                        )
                        return CircuitState.HALF_OPEN

            return state

        except Exception as exc:
            logger.warning(
                "circuit_breaker.redis_error",
                extra={"domain": domain, "error": str(exc)[:120]},
            )
            return CircuitState.CLOSED  # fail-open

    async def check_and_raise(self, domain: str) -> None:
        """Verifica el estado del circuit. Lanza ScraperCircuitOpenError si OPEN."""
        state = await self.get_state(domain)
        if state == CircuitState.OPEN:
            raise ScraperCircuitOpenError(domain)

    async def record_success(self, domain: str) -> None:
        """Registra éxito — resetea el contador de fallos y cierra el circuit."""
        try:
            r = await self._get_redis()
            state_key, failures_key, opened_at_key = self._keys(domain)

            await r.delete(state_key, failures_key, opened_at_key)
            logger.debug("circuit_breaker.success", extra={"domain": domain})

        except Exception as exc:
            logger.warning(
                "circuit_breaker.record_success_error",
                extra={"domain": domain, "error": str(exc)[:120]},
            )

    async def record_failure(self, domain: str) -> CircuitState:
        """Registra un fallo. Si supera el threshold, abre el circuit.

        Returns:
            Estado del circuit después de registrar el fallo.
        """
        try:
            r = await self._get_redis()
            state_key, failures_key, opened_at_key = self._keys(domain)

            # Incrementar fallos con TTL de ventana
            failures = await r.incr(failures_key)
            await r.expire(failures_key, self._failure_window)

            logger.debug(
                "circuit_breaker.failure_recorded",
                extra={"domain": domain, "failures": failures, "threshold": self._failure_threshold},
            )

            if failures >= self._failure_threshold:
                await r.set(state_key, CircuitState.OPEN, ex=self._recovery_timeout * 3)
                await r.set(opened_at_key, str(time.time()), ex=self._recovery_timeout * 3)
                logger.warning(
                    "circuit_breaker.opened",
                    extra={"domain": domain, "failures": failures},
                )
                return CircuitState.OPEN

            return CircuitState.CLOSED

        except Exception as exc:
            logger.warning(
                "circuit_breaker.record_failure_error",
                extra={"domain": domain, "error": str(exc)[:120]},
            )
            return CircuitState.CLOSED

    async def get_stats(self, domain: str) -> dict:
        """Devuelve estadísticas del circuit para un dominio."""
        try:
            r = await self._get_redis()
            state_key, failures_key, opened_at_key = self._keys(domain)

            state_raw, failures_raw, opened_at_raw = await r.mget(
                state_key, failures_key, opened_at_key
            )
            state = CircuitState(state_raw) if state_raw else CircuitState.CLOSED
            failures = int(failures_raw) if failures_raw else 0
            opened_at = float(opened_at_raw) if opened_at_raw else None

            return {
                "domain": domain,
                "state": state.value,
                "failures": failures,
                "failure_threshold": self._failure_threshold,
                "opened_at": opened_at,
                "recovery_timeout": self._recovery_timeout,
            }
        except Exception as exc:
            logger.warning("circuit_breaker.stats_error", extra={"domain": domain, "error": str(exc)[:120]})
            return {
                "domain": domain,
                "state": "unknown",
                "failures": 0,
                "failure_threshold": self._failure_threshold,
                "opened_at": None,
                "recovery_timeout": self._recovery_timeout,
            }

    async def force_close(self, domain: str) -> None:
        """Fuerza el circuit a CLOSED (para admin/recovery manual)."""
        try:
            r = await self._get_redis()
            state_key, failures_key, opened_at_key = self._keys(domain)
            await r.delete(state_key, failures_key, opened_at_key)
            logger.info("circuit_breaker.force_closed", extra={"domain": domain})
        except Exception as exc:
            logger.warning("circuit_breaker.force_close_error", extra={"domain": domain, "error": str(exc)[:120]})

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


# ---------------------------------------------------------------------------
# Proxy Pool
# ---------------------------------------------------------------------------


class ProxyPool:
    """Pool de proxies distribuido en Redis usando rotación LPUSH/RPOP.

    Key Redis: ``proxy_pool`` (lista)

    Rotación:
        - ``get_proxy()`` hace RPOP + LPUSH (round-robin circulares)
        - Si el pool está vacío, retorna None (sin proxy)
    """

    def __init__(self, redis_url: str) -> None:
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None

    async def _get_redis(self) -> aioredis.Redis:
        if self._redis is None:
            self._redis = aioredis.from_url(
                self._redis_url,
                encoding="utf-8",
                decode_responses=True,
            )
        return self._redis

    async def get_proxy(self) -> str | None:
        """Obtiene el siguiente proxy (round-robin). Retorna None si el pool está vacío."""
        try:
            r = await self._get_redis()
            proxy = await r.rpoplpush(PROXY_POOL_KEY, PROXY_POOL_KEY)  # type: ignore[attr-defined]
            return proxy
        except Exception as exc:
            logger.warning("proxy_pool.get_error", extra={"error": str(exc)[:120]})
            return None

    async def add_proxy(self, proxy: str) -> int:
        """Añade un proxy al pool. Retorna el tamaño actual del pool."""
        r = await self._get_redis()
        return await r.lpush(PROXY_POOL_KEY, proxy)

    async def remove_proxy(self, proxy: str) -> int:
        """Elimina todas las ocurrencias del proxy del pool. Retorna cuántos se eliminaron."""
        r = await self._get_redis()
        return await r.lrem(PROXY_POOL_KEY, 0, proxy)

    async def list_proxies(self) -> list[str]:
        """Lista todos los proxies del pool."""
        try:
            r = await self._get_redis()
            return await r.lrange(PROXY_POOL_KEY, 0, -1)
        except Exception as exc:
            logger.warning("proxy_pool.list_error", extra={"error": str(exc)[:120]})
            return []

    async def size(self) -> int:
        """Retorna el número de proxies en el pool."""
        try:
            r = await self._get_redis()
            return await r.llen(PROXY_POOL_KEY)
        except Exception:
            return 0

    async def close(self) -> None:
        if self._redis is not None:
            await self._redis.aclose()
            self._redis = None


# ---------------------------------------------------------------------------
# Singletons lazy
# ---------------------------------------------------------------------------

_circuit_breaker_instance: CircuitBreaker | None = None
_proxy_pool_instance: ProxyPool | None = None


def get_circuit_breaker() -> CircuitBreaker:
    global _circuit_breaker_instance
    if _circuit_breaker_instance is None:
        from app.core.config import settings

        _circuit_breaker_instance = CircuitBreaker(
            redis_url=str(settings.REDIS_URL),
            failure_threshold=getattr(settings, "SCRAPER_CB_FAILURE_THRESHOLD", 5),
            recovery_timeout=getattr(settings, "SCRAPER_CB_RECOVERY_TIMEOUT", 60),
        )
    return _circuit_breaker_instance


def get_proxy_pool() -> ProxyPool:
    global _proxy_pool_instance
    if _proxy_pool_instance is None:
        from app.core.config import settings

        _proxy_pool_instance = ProxyPool(redis_url=str(settings.REDIS_URL))
    return _proxy_pool_instance
