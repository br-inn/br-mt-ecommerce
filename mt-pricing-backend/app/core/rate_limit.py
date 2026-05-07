"""Rate limiting — middleware ASGI con token bucket Redis-backed.

US-1A-SEC-01 (Sprint 5, ADR-079).

Decisión técnica (ADR-079 §rate-limit-algorithm):

- **Token bucket** elegido sobre sliding-window y leaky bucket por:
  1. Soporta bursts cortos (capacity > refill rate) — comportamiento humano
     en UI (ráfaga de clicks tras login) sin pegar 429s falsos.
  2. Memoria O(1) por key vs O(N requests) de sliding-window.
  3. Implementable atómicamente en una sola RTT a Redis con un script Lua
     (sin race conditions entre check + decrement).
  4. Más amigable a UX que leaky bucket (que serializa estrictamente).

Modelo:

- Key:  ``rl:{scope}:{client_id}``     — scope p.ej. "api", "auth".
- Capacity (bucket size) y refill rate (tokens/segundo) configurables por
  scope. Defaults pensados para Fase 1 (≤30 usuarios MT internos):

  =========== ========== =================
  Scope       Capacity   Refill (tok/sec)
  =========== ========== =================
  default      120        2.0
  auth          20        0.5
  =========== ========== =================

- Cliente identificado por header ``X-User-Id`` post-auth, fallback a
  ``X-Real-IP`` / client.host. Caddy ya inyecta ``X-Real-IP`` (ver
  ``Caddyfile``).

- Si Redis está caído o el script falla, **fail-open**: log warning y dejar
  pasar — preferimos disponibilidad sobre seguridad estricta en Fase 1.
  Para producción real considerar fail-closed con circuit breaker.

Tests: ``tests/unit/core/test_rate_limit.py``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from starlette.requests import Request
    from starlette.responses import Response
    from starlette.types import ASGIApp


logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Lua script — atomic token-bucket consume.
# ---------------------------------------------------------------------------
# KEYS[1] = bucket key
# ARGV[1] = capacity        (max tokens)
# ARGV[2] = refill_rate     (tokens/second, float as string)
# ARGV[3] = now             (unix epoch seconds, float)
# ARGV[4] = cost            (tokens to consume, default 1)
#
# Returns: { allowed (1|0), tokens_remaining (float), retry_after_s (float) }
_LUA_TOKEN_BUCKET = """
local key = KEYS[1]
local capacity = tonumber(ARGV[1])
local refill_rate = tonumber(ARGV[2])
local now = tonumber(ARGV[3])
local cost = tonumber(ARGV[4])

local data = redis.call('HMGET', key, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])

if tokens == nil then
    tokens = capacity
    ts = now
end

-- Refill since last touch.
local delta = math.max(0, now - ts)
tokens = math.min(capacity, tokens + delta * refill_rate)

local allowed = 0
local retry_after = 0
if tokens >= cost then
    tokens = tokens - cost
    allowed = 1
else
    if refill_rate > 0 then
        retry_after = (cost - tokens) / refill_rate
    else
        retry_after = -1
    end
end

redis.call('HMSET', key, 'tokens', tokens, 'ts', now)
-- TTL = 2x time to fill from empty (seguridad para keys huérfanas).
local ttl
if refill_rate > 0 then
    ttl = math.ceil((capacity / refill_rate) * 2)
else
    ttl = 60
end
redis.call('EXPIRE', key, ttl)

return { allowed, tostring(tokens), tostring(retry_after) }
"""


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RateLimitPolicy:
    """Política por scope — capacity (bucket size) + refill rate."""

    capacity: int
    refill_per_sec: float


DEFAULT_POLICIES: dict[str, RateLimitPolicy] = {
    "default": RateLimitPolicy(capacity=120, refill_per_sec=2.0),
    "auth": RateLimitPolicy(capacity=20, refill_per_sec=0.5),
}


# ---------------------------------------------------------------------------
# Limiter
# ---------------------------------------------------------------------------
class TokenBucketLimiter:
    """Wrapper sobre Redis ejecutando el script Lua de manera idempotente.

    El cliente Redis se inyecta — facilita tests con ``fakeredis`` y con
    fakes in-memory simples (cualquier objeto con ``eval(script, keys=,
    args=)`` o ``evalsha`` async).
    """

    def __init__(
        self,
        redis_client: Any,
        policies: dict[str, RateLimitPolicy] | None = None,
    ) -> None:
        self._redis = redis_client
        self._policies = policies or DEFAULT_POLICIES

    def policy_for(self, scope: str) -> RateLimitPolicy:
        return self._policies.get(scope, self._policies["default"])

    async def check(
        self,
        *,
        scope: str,
        client_id: str,
        cost: int = 1,
        now: float | None = None,
    ) -> tuple[bool, float, float]:
        """Devuelve ``(allowed, tokens_remaining, retry_after_s)``.

        Args:
            scope: namespace lógico (``"api"``, ``"auth"``, ...).
            client_id: ID del consumidor (user-id o IP).
            cost: tokens a consumir (>=1).
            now: override de ``time.time()`` para tests deterministas.

        Notas:
            - **Fail-open**: si el script Lua/Redis falla, log + permite. El
              caller decide si vigilar la métrica de excepciones.
        """
        policy = self.policy_for(scope)
        ts = time.time() if now is None else now
        key = f"rl:{scope}:{client_id}"

        try:
            raw = await self._eval(
                _LUA_TOKEN_BUCKET,
                keys=[key],
                args=[
                    str(policy.capacity),
                    str(policy.refill_per_sec),
                    f"{ts:.6f}",
                    str(cost),
                ],
            )
        except Exception as exc:  # noqa: BLE001 — fail-open
            logger.warning("rate_limit.redis_error fail-open: %s", exc)
            return True, float(policy.capacity), 0.0

        allowed_raw, tokens_raw, retry_raw = _unpack_lua_result(raw)
        return (
            int(allowed_raw) == 1,
            float(tokens_raw),
            float(retry_raw),
        )

    async def _eval(
        self,
        script: str,
        *,
        keys: list[str],
        args: list[str],
    ) -> Any:
        """Adapter — soporta tanto ``redis.asyncio.Redis`` como fakes sync."""
        eval_fn = getattr(self._redis, "eval", None)
        if eval_fn is None:
            raise RuntimeError(
                "Redis client no soporta eval() — provee un cliente compatible."
            )
        result = eval_fn(script, len(keys), *keys, *args)
        # ``redis.asyncio.Redis.eval`` devuelve coroutine; fakes podrían ser sync.
        if hasattr(result, "__await__"):
            return await result
        return result


def _unpack_lua_result(raw: Any) -> tuple[Any, Any, Any]:
    """``redis-py`` devuelve list[bytes|int|str]; normalizamos a 3-tuple."""
    if isinstance(raw, (list, tuple)) and len(raw) >= 3:
        return raw[0], raw[1], raw[2]
    raise RuntimeError(f"Resultado Lua inesperado: {raw!r}")


# ---------------------------------------------------------------------------
# ASGI middleware
# ---------------------------------------------------------------------------
class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware FastAPI que aplica rate limiting por path-prefix scope.

    Reglas de scope:

    - ``/auth/*`` y ``/api/v1/auth/*``    → scope ``auth``  (refill lento).
    - cualquier otra ruta API              → scope ``default``.
    - ``/health/*``, ``/metrics``          → bypass (no se limitan).

    Identificación del cliente:

    1. Header ``X-User-Id`` si está presente (set por dependency JWT
       upstream). Permite limitar por usuario aplicativo aún detrás de NAT.
    2. Header ``X-Real-IP`` (Caddy lo setea — ver ``Caddyfile``).
    3. ``request.client.host`` (fallback ASGI).
    4. ``"anonymous"`` si nada de lo anterior.
    """

    BYPASS_PREFIXES: tuple[str, ...] = ("/health/", "/metrics")
    AUTH_PREFIXES: tuple[str, ...] = ("/auth/", "/api/v1/auth/")

    def __init__(
        self,
        app: ASGIApp,
        limiter: TokenBucketLimiter,
        *,
        enabled: bool = True,
    ) -> None:
        super().__init__(app)
        self._limiter = limiter
        self._enabled = enabled

    @classmethod
    def scope_for_path(cls, path: str) -> str | None:
        """Devuelve el scope o ``None`` si la ruta debe bypassearse."""
        for prefix in cls.BYPASS_PREFIXES:
            if path.startswith(prefix):
                return None
        for prefix in cls.AUTH_PREFIXES:
            if path.startswith(prefix):
                return "auth"
        return "default"

    @staticmethod
    def client_id_from(request: Request) -> str:
        """Extrae el identificador del cliente (header > IP > anon)."""
        user_id = request.headers.get("X-User-Id")
        if user_id:
            return f"u:{user_id}"
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return f"ip:{real_ip}"
        if request.client and request.client.host:
            return f"ip:{request.client.host}"
        return "anonymous"

    async def dispatch(  # type: ignore[override]
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        if not self._enabled:
            return await call_next(request)

        scope = self.scope_for_path(request.url.path)
        if scope is None:
            return await call_next(request)

        client_id = self.client_id_from(request)
        allowed, tokens, retry = await self._limiter.check(
            scope=scope,
            client_id=client_id,
        )
        if allowed:
            response = await call_next(request)
            policy = self._limiter.policy_for(scope)
            response.headers["X-RateLimit-Limit"] = str(policy.capacity)
            response.headers["X-RateLimit-Remaining"] = str(int(tokens))
            return response

        retry_after = max(1, int(retry + 1)) if retry > 0 else 1
        return JSONResponse(
            status_code=429,
            content={
                "type": "https://mtme.ae/errors/rate-limited",
                "title": "Too many requests",
                "status": 429,
                "detail": f"Rate limit excedido para scope '{scope}'.",
                "retry_after_seconds": retry_after,
            },
            headers={"Retry-After": str(retry_after)},
        )


__all__ = [
    "DEFAULT_POLICIES",
    "RateLimitMiddleware",
    "RateLimitPolicy",
    "TokenBucketLimiter",
]
