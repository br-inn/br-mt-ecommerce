"""Unit tests del middleware token-bucket Redis-backed.

US-1A-SEC-01 (Sprint 5).

Cubre:

- Token bucket consume + refill correcto.
- Capacity respetada (no se acumulan tokens > capacity).
- Burst hasta capacity, luego 429.
- Bypass de ``/health/*`` y ``/metrics``.
- Scope ``auth`` con política más estricta.
- Retry-After header poblado.
- Fail-open si Redis falla.
- ASGI middleware integration end-to-end (FastAPI ad-hoc).
"""

from __future__ import annotations

from typing import Any

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.rate_limit import (
    DEFAULT_POLICIES,
    RateLimitMiddleware,
    RateLimitPolicy,
    TokenBucketLimiter,
)

pytestmark = pytest.mark.unit


# ---------------------------------------------------------------------------
# Fake Redis — implementa SOLO `eval(script, num_keys, *keys, *args)` en
# memoria, ejecutando la lógica del Lua script de manera equivalente.
# ---------------------------------------------------------------------------
class _FakeRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self._buckets: dict[str, dict[str, float]] = {}
        self._fail = fail

    def eval(self, script: str, num_keys: int, *args: Any) -> list[Any]:
        if self._fail:
            raise RuntimeError("simulated redis failure")
        keys = list(args[:num_keys])
        argv = list(args[num_keys:])
        key = keys[0]
        capacity = float(argv[0])
        refill = float(argv[1])
        now = float(argv[2])
        cost = float(argv[3])

        bucket = self._buckets.setdefault(key, {"tokens": capacity, "ts": now})
        delta = max(0.0, now - bucket["ts"])
        tokens = min(capacity, bucket["tokens"] + delta * refill)

        if tokens >= cost:
            tokens -= cost
            allowed = 1
            retry_after = 0.0
        else:
            allowed = 0
            retry_after = (cost - tokens) / refill if refill > 0 else -1.0

        bucket["tokens"] = tokens
        bucket["ts"] = now
        return [allowed, str(tokens), str(retry_after)]


# ---------------------------------------------------------------------------
# 1. Burst hasta capacity, luego 429.
# ---------------------------------------------------------------------------
async def test_token_bucket_burst_then_denies() -> None:
    redis = _FakeRedis()
    policies = {
        "default": RateLimitPolicy(capacity=3, refill_per_sec=0.0),
    }
    limiter = TokenBucketLimiter(redis, policies=policies)

    results = []
    for _ in range(5):
        allowed, _tok, _retry = await limiter.check(scope="default", client_id="alice", now=1000.0)
        results.append(allowed)
    assert results == [True, True, True, False, False]


# ---------------------------------------------------------------------------
# 2. Refill devuelve permisos tras un intervalo.
# ---------------------------------------------------------------------------
async def test_token_bucket_refills_over_time() -> None:
    redis = _FakeRedis()
    policies = {
        "default": RateLimitPolicy(capacity=2, refill_per_sec=1.0),
    }
    limiter = TokenBucketLimiter(redis, policies=policies)

    # Quemar la capacity.
    a1, *_ = await limiter.check(scope="default", client_id="bob", now=100.0)
    a2, *_ = await limiter.check(scope="default", client_id="bob", now=100.0)
    a3, *_ = await limiter.check(scope="default", client_id="bob", now=100.0)
    assert (a1, a2, a3) == (True, True, False)

    # Tras 2s deberían haberse repuesto 2 tokens.
    a4, _tok, _r = await limiter.check(scope="default", client_id="bob", now=102.0)
    a5, _tok, _r = await limiter.check(scope="default", client_id="bob", now=102.0)
    assert (a4, a5) == (True, True)


# ---------------------------------------------------------------------------
# 3. Buckets independientes por client_id.
# ---------------------------------------------------------------------------
async def test_buckets_isolated_per_client() -> None:
    redis = _FakeRedis()
    policies = {
        "default": RateLimitPolicy(capacity=1, refill_per_sec=0.0),
    }
    limiter = TokenBucketLimiter(redis, policies=policies)

    a1, *_ = await limiter.check(scope="default", client_id="alice", now=0.0)
    a2, *_ = await limiter.check(scope="default", client_id="alice", now=0.0)
    a3, *_ = await limiter.check(scope="default", client_id="bob", now=0.0)
    assert (a1, a2, a3) == (True, False, True)


# ---------------------------------------------------------------------------
# 4. Fail-open si Redis revienta.
# ---------------------------------------------------------------------------
async def test_fails_open_on_redis_error() -> None:
    redis = _FakeRedis(fail=True)
    limiter = TokenBucketLimiter(redis)

    allowed, tokens, retry = await limiter.check(scope="default", client_id="ip:1.2.3.4")
    assert allowed is True
    assert tokens == float(DEFAULT_POLICIES["default"].capacity)
    assert retry == 0.0


# ---------------------------------------------------------------------------
# 5. ASGI middleware — bypass de /health/* y /metrics.
# ---------------------------------------------------------------------------
def _build_app(limiter: TokenBucketLimiter) -> FastAPI:
    app = FastAPI()
    app.add_middleware(RateLimitMiddleware, limiter=limiter)

    @app.get("/api/v1/ping")
    async def ping() -> dict[str, str]:
        return {"ok": "yes"}

    @app.get("/health/live")
    async def live() -> dict[str, str]:
        return {"healthy": "yes"}

    @app.get("/metrics")
    async def metrics() -> dict[str, int]:
        return {"n": 1}

    @app.post("/api/v1/auth/login")
    async def login() -> dict[str, str]:
        return {"token": "xyz"}

    return app


async def test_middleware_bypasses_health_and_metrics() -> None:
    redis = _FakeRedis()
    policies = {
        "default": RateLimitPolicy(capacity=1, refill_per_sec=0.0),
        "auth": RateLimitPolicy(capacity=1, refill_per_sec=0.0),
    }
    limiter = TokenBucketLimiter(redis, policies=policies)
    app = _build_app(limiter)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        # 5 hits a /health/live — todos 200, ningún 429.
        for _ in range(5):
            r = await ac.get("/health/live")
            assert r.status_code == 200
        for _ in range(5):
            r = await ac.get("/metrics")
            assert r.status_code == 200


# ---------------------------------------------------------------------------
# 6. ASGI middleware — devuelve 429 con Retry-After al exceder.
# ---------------------------------------------------------------------------
async def test_middleware_returns_429_when_exceeded() -> None:
    redis = _FakeRedis()
    policies = {
        "default": RateLimitPolicy(capacity=2, refill_per_sec=1.0),
        "auth": RateLimitPolicy(capacity=1, refill_per_sec=0.5),
    }
    limiter = TokenBucketLimiter(redis, policies=policies)
    app = _build_app(limiter)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://t") as ac:
        # Las 2 primeras pasan, la 3ra debe ser 429.
        r1 = await ac.get("/api/v1/ping", headers={"X-User-Id": "u1"})
        r2 = await ac.get("/api/v1/ping", headers={"X-User-Id": "u1"})
        r3 = await ac.get("/api/v1/ping", headers={"X-User-Id": "u1"})
        assert r1.status_code == 200
        assert r2.status_code == 200
        assert r3.status_code == 429, r3.text
        assert r3.headers.get("Retry-After") is not None
        assert int(r3.headers["Retry-After"]) >= 1
        body = r3.json()
        assert body["status"] == 429
        assert body["title"] == "Too many requests"


# ---------------------------------------------------------------------------
# 7. Scope detection — /auth/* usa bucket más estricto.
# ---------------------------------------------------------------------------
def test_scope_for_path_classifies_auth_and_bypass() -> None:
    assert RateLimitMiddleware.scope_for_path("/health/live") is None
    assert RateLimitMiddleware.scope_for_path("/metrics") is None
    assert RateLimitMiddleware.scope_for_path("/api/v1/auth/login") == "auth"
    assert RateLimitMiddleware.scope_for_path("/auth/refresh") == "auth"
    assert RateLimitMiddleware.scope_for_path("/api/v1/products") == "default"


# ---------------------------------------------------------------------------
# 8. client_id_from — prioriza X-User-Id sobre IP.
# ---------------------------------------------------------------------------
async def test_client_id_priority_user_over_ip() -> None:
    from starlette.requests import Request

    scope = {
        "type": "http",
        "headers": [
            (b"x-user-id", b"u-42"),
            (b"x-real-ip", b"1.2.3.4"),
        ],
        "client": ("9.9.9.9", 12345),
    }
    req = Request(scope)
    assert RateLimitMiddleware.client_id_from(req) == "u:u-42"

    # Sin X-User-Id pero con X-Real-IP.
    scope2 = {
        "type": "http",
        "headers": [(b"x-real-ip", b"1.2.3.4")],
        "client": ("9.9.9.9", 12345),
    }
    req2 = Request(scope2)
    assert RateLimitMiddleware.client_id_from(req2) == "ip:1.2.3.4"

    # Sin nada.
    scope3 = {
        "type": "http",
        "headers": [],
        "client": None,
    }
    req3 = Request(scope3)
    assert RateLimitMiddleware.client_id_from(req3) == "anonymous"
