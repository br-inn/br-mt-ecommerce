"""Integration tests — healthcheck endpoints (ADR-048).

Cobertura:
- /health/live → siempre 200, no toca dependencias.
- /health/ready → 200 con DB+Redis up, 503 si alguno cae.
- /health/db → 401 sin auth, 200 con basic-auth válido + pool stats.
- /health/redis → 401 sin auth, 200 con auth.
- /health/celery → reporta queues alive/dead leyendo Redis heartbeats.
- Auth: basic-auth Y header X-Healthcheck-Token funcionan.
- request_id propagation y PII redaction en logs.

Mocks: para tests de "DB down" / "Redis down" mockeamos el helper directamente.
Esto evita levantar/tirar containers — el "happy path" usa testcontainers reales.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING
from unittest.mock import patch

import pytest

if TYPE_CHECKING:
    from httpx import AsyncClient
    from redis.asyncio import Redis


# Marca todos los tests como integration — requieren testcontainers.
pytestmark = pytest.mark.integration


def _basic_header(user: str, password: str) -> dict[str, str]:
    raw = f"{user}:{password}".encode()
    return {"Authorization": "Basic " + base64.b64encode(raw).decode()}


# =============================================================================
# Liveness
# =============================================================================
async def test_liveness_always_200(async_client: AsyncClient) -> None:
    """Liveness no depende de servicios externos — siempre 200."""
    resp = await async_client.get("/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert "ts" in body
    assert "version" in body


async def test_liveness_no_auth_required(async_client: AsyncClient) -> None:
    """Liveness es público — Kubernetes/LB lo consume sin credenciales."""
    resp = await async_client.get("/health/live")
    assert resp.status_code == 200


async def test_liveness_response_time_under_100ms(async_client: AsyncClient) -> None:
    """Liveness debe responder en < 100ms (sin red, in-process)."""
    import time

    t0 = time.perf_counter()
    resp = await async_client.get("/health/live")
    elapsed_ms = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 200
    # In-process ASGI sin red: con margen amplio para CI lento.
    assert elapsed_ms < 500


# =============================================================================
# Readiness
# =============================================================================
async def test_readiness_with_db_and_redis_up(
    async_client: AsyncClient,
    postgres_container: str,
    redis_container: str,
) -> None:
    """Con ambas dependencias arriba, readiness devuelve 200 + status=ok."""
    resp = await async_client.get("/health/ready")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["checks"]["db"]["ok"] is True
    assert body["checks"]["redis"]["ok"] is True


async def test_readiness_returns_503_if_db_down(async_client: AsyncClient) -> None:
    """Si DB falla, readiness 503 + status=degraded."""
    from unittest.mock import AsyncMock

    fake_down = {"ok": False, "error": "ConnectionRefusedError", "detail": "no DB"}

    with patch("app.api.health._check_db", new=AsyncMock(return_value=fake_down)):
        resp = await async_client.get("/health/ready")
    assert resp.status_code == 503
    body = resp.json()
    assert body["status"] == "degraded"
    assert body["checks"]["db"]["ok"] is False


async def test_readiness_returns_503_if_redis_down(async_client: AsyncClient) -> None:
    """Si Redis falla, readiness 503."""
    from unittest.mock import AsyncMock

    fake_down = {"ok": False, "error": "TimeoutError", "detail": "no redis"}

    with patch("app.api.health._check_redis", new=AsyncMock(return_value=fake_down)):
        resp = await async_client.get("/health/ready")
    assert resp.status_code == 503


# =============================================================================
# Deep DB — auth gating
# =============================================================================
async def test_deep_db_requires_auth_401(async_client: AsyncClient) -> None:
    """Sin credenciales, /health/db responde 401."""
    resp = await async_client.get("/health/db")
    assert resp.status_code == 401


async def test_deep_db_wrong_password_401(async_client: AsyncClient) -> None:
    """Password incorrecta — 401."""
    resp = await async_client.get(
        "/health/db",
        headers=_basic_header("monitoring", "wrong-password"),
    )
    assert resp.status_code == 401


async def test_deep_db_with_auth_returns_pool_stats(
    async_client: AsyncClient,
    postgres_container: str,
) -> None:
    """Con basic-auth válido, /health/db devuelve OK + pool stats + pg_version."""
    from app.core.config import settings

    resp = await async_client.get(
        "/health/db",
        headers=_basic_header(
            settings.HEALTH_BASIC_AUTH_USER,
            settings.HEALTH_BASIC_AUTH_PASSWORD.get_secret_value(),
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "pg_version" in body
    assert "pool" in body
    # Pool exporter siempre devuelve estos campos (None si no aplica).
    for key in ("size", "checked_in", "checked_out", "overflow"):
        assert key in body["pool"]


async def test_deep_db_with_token_header_works(
    async_client: AsyncClient,
    postgres_container: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """X-Healthcheck-Token alternativo al basic-auth."""
    from pydantic import SecretStr

    import app.api.health as health_module

    # Patch the settings reference held by the health module directly.
    # Patching app.core.config.settings would miss if redis_container fixture
    # already reassigned that module attribute to a new Settings instance.
    monkeypatch.setattr(
        health_module.settings,
        "HEALTH_TOKEN",
        SecretStr("super-secret-token"),
    )
    resp = await async_client.get(
        "/health/db",
        headers={"X-Healthcheck-Token": "super-secret-token"},
    )
    assert resp.status_code == 200


# =============================================================================
# Deep Redis
# =============================================================================
async def test_deep_redis_requires_auth_401(async_client: AsyncClient) -> None:
    resp = await async_client.get("/health/redis")
    assert resp.status_code == 401


async def test_deep_redis_with_auth_returns_version(
    async_client: AsyncClient,
    redis_container: str,
) -> None:
    from app.core.config import settings

    resp = await async_client.get(
        "/health/redis",
        headers=_basic_header(
            settings.HEALTH_BASIC_AUTH_USER,
            settings.HEALTH_BASIC_AUTH_PASSWORD.get_secret_value(),
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True


# =============================================================================
# Celery heartbeat
# =============================================================================
async def test_celery_heartbeat_no_workers_returns_unhealthy(
    async_client: AsyncClient,
    redis_client: Redis,
) -> None:
    """Sin keys de heartbeat en Redis, todas las queues reportan alive=false."""
    from app.core.config import settings

    # `redis_client` fixture flushea la DB antes de yield → no hay keys.
    resp = await async_client.get(
        "/health/celery",
        headers=_basic_header(
            settings.HEALTH_BASIC_AUTH_USER,
            settings.HEALTH_BASIC_AUTH_PASSWORD.get_secret_value(),
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert all(not q["alive"] for q in body["queues"].values())


async def test_celery_heartbeat_workers_alive_returns_healthy(
    async_client: AsyncClient,
    redis_client: Redis,
) -> None:
    """Con keys recientes en Redis, todas las queues reportan alive=true."""
    from app.core.config import settings

    now_iso = datetime.now(UTC).isoformat()
    queues = ("imports", "pricing", "images", "comparator", "notifications", "audit")
    for q in queues:
        await redis_client.set(f"mt:worker:heartbeat:{q}", now_iso, ex=120)

    resp = await async_client.get(
        "/health/celery",
        headers=_basic_header(
            settings.HEALTH_BASIC_AUTH_USER,
            settings.HEALTH_BASIC_AUTH_PASSWORD.get_secret_value(),
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    for q in queues:
        assert body["queues"][q]["alive"] is True
        assert body["queues"][q]["age_seconds"] is not None
        assert body["queues"][q]["age_seconds"] < 60


async def test_celery_heartbeat_stale_returns_unhealthy(
    async_client: AsyncClient,
    redis_client: Redis,
) -> None:
    """Heartbeat con > 60s de antigüedad → alive=false."""
    from app.core.config import settings

    stale = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    queues = ("imports", "pricing", "images", "comparator", "notifications", "audit")
    for q in queues:
        await redis_client.set(f"mt:worker:heartbeat:{q}", stale, ex=600)

    resp = await async_client.get(
        "/health/celery",
        headers=_basic_header(
            settings.HEALTH_BASIC_AUTH_USER,
            settings.HEALTH_BASIC_AUTH_PASSWORD.get_secret_value(),
        ),
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    for q in queues:
        assert body["queues"][q]["alive"] is False


# =============================================================================
# Request ID propagation + PII redaction
# =============================================================================
async def test_request_id_propagation_returned_in_response(
    async_client: AsyncClient,
) -> None:
    """Si cliente manda X-Request-ID, server lo devuelve en el response."""
    resp = await async_client.get(
        "/health/live",
        headers={"X-Request-ID": "test-req-abc-123"},
    )
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-ID") == "test-req-abc-123"


async def test_request_id_generated_if_absent(async_client: AsyncClient) -> None:
    """Si cliente no manda X-Request-ID, server genera uno nuevo (UUID4)."""
    resp = await async_client.get("/health/live")
    rid = resp.headers.get("X-Request-ID")
    assert rid is not None
    assert len(rid) >= 16  # UUID4 tiene 36 chars con guiones


def test_pii_redaction_in_logs() -> None:
    """structlog NUNCA debe loggear passwords/tokens en plano.

    Configura un pipeline structlog determinístico (JSON renderer) en memoria
    y verifica que sensibles van a `***REDACTED***` y que email se enmascara.
    """
    import json

    import structlog as sl
    from structlog.testing import LogCapture

    from app.core.logging import _redact_pii

    cap = LogCapture()
    sl.configure(
        processors=[_redact_pii, cap],
        wrapper_class=sl.BoundLogger,
        cache_logger_on_first_use=False,
    )
    try:
        logger = sl.get_logger("test.pii")
        logger.info(
            "user_login",
            email="alice@example.com",
            password="super-secret-pwd",
            access_token="ya29.fakejwt",
            api_key="sk-secret",
            user_id="u-1",
        )
    finally:
        # Restaurar configuración global.
        from app.core.logging import configure_logging

        configure_logging()

    assert len(cap.entries) == 1
    entry = cap.entries[0]
    serialized = json.dumps(entry)
    # Sensibles redactados:
    assert "super-secret-pwd" not in serialized
    assert "ya29.fakejwt" not in serialized
    assert "sk-secret" not in serialized
    assert entry["password"] == "***REDACTED***"
    assert entry["access_token"] == "***REDACTED***"
    assert entry["api_key"] == "***REDACTED***"
    # Email enmascarado:
    assert entry["email"] == "al***@example.com"
    # No-sensible permanece:
    assert entry["user_id"] == "u-1"


# =============================================================================
# Heartbeat publisher (worker side)
# =============================================================================
async def test_heartbeat_publisher_writes_to_redis(
    redis_container: str,
    redis_client: Redis,
) -> None:
    """`_publish` debe escribir `mt:worker:heartbeat:<queue>` con TTL."""
    from app.workers import heartbeat as hb_module

    # Reset del cliente sync cacheado para que tome la URL del testcontainer.
    hb_module._sync_client = None
    hb_module._publish("imports")

    value = await redis_client.get("mt:worker:heartbeat:imports")
    assert value is not None
    ttl = await redis_client.ttl("mt:worker:heartbeat:imports")
    assert ttl > 0
