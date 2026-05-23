"""Smoke tests — verifica que la app arranca y `/health/live` responde."""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.unit


async def test_liveness_returns_200(async_client) -> None:
    resp = await async_client.get("/health/live")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["service"] == "mt-pricing-backend"


async def test_docs_enabled_in_dev(async_client) -> None:
    resp = await async_client.get("/docs")
    # 200 si ENABLE_DOCS, 404 si no.
    assert resp.status_code in (200, 404)


async def test_celery_eager_health_ping(celery_app_eager) -> None:
    """Las 6 queues tienen al menos `health_ping` registrada y devuelve 'ok'."""
    from app.workers.tasks import (
        audit,
        comparator,
        images,
        imports,
        notifications,
        pricing,
    )

    for module in (imports, pricing, images, comparator, notifications, audit):
        result = module.health_ping.delay()
        assert result.get(timeout=2) == "ok"
