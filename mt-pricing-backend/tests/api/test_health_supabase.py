"""Tests para el chequeo opcional de Supabase Auth en `/health/ready`.

Complementa `tests/integration/test_health.py` (ya cubre live/ready/db/redis)
con cobertura específica para el ping a Supabase Auth añadido en US-1A-07-02-S1.

Cobertura:
- Sin `SUPABASE_AUTH_HEALTH_URL` → check skipped, `ok=True`, no afecta status.
- Con URL válida y respuesta 200 → check ok.
- Con URL configurada y exception → check fails → /health/ready devuelve 503.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_supabase_auth_check_skipped_when_url_empty() -> None:
    from app.api.health import _check_supabase_auth
    from app.core.config import settings

    prev = settings.SUPABASE_AUTH_HEALTH_URL
    settings.SUPABASE_AUTH_HEALTH_URL = ""
    try:
        result = await _check_supabase_auth(timeout=2.0)
    finally:
        settings.SUPABASE_AUTH_HEALTH_URL = prev

    assert result["ok"] is True
    assert result["skipped"] is True


@pytest.mark.unit
@pytest.mark.asyncio
async def test_supabase_auth_check_returns_ok_on_2xx() -> None:
    from app.api.health import _check_supabase_auth
    from app.core.config import settings

    prev = settings.SUPABASE_AUTH_HEALTH_URL
    settings.SUPABASE_AUTH_HEALTH_URL = "https://test.supabase.co/auth/v1/health"

    fake_resp = type("R", (), {"status_code": 200})()
    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.get = AsyncMock(return_value=fake_resp)

    try:
        with patch("httpx.AsyncClient", return_value=fake_client):
            result = await _check_supabase_auth(timeout=2.0)
    finally:
        settings.SUPABASE_AUTH_HEALTH_URL = prev

    assert result["ok"] is True
    assert result["status_code"] == 200


@pytest.mark.unit
@pytest.mark.asyncio
async def test_supabase_auth_check_fails_on_exception() -> None:
    from app.api.health import _check_supabase_auth
    from app.core.config import settings

    prev = settings.SUPABASE_AUTH_HEALTH_URL
    settings.SUPABASE_AUTH_HEALTH_URL = "https://test.supabase.co/auth/v1/health"

    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.get = AsyncMock(side_effect=ConnectionError("connection refused"))

    try:
        with patch("httpx.AsyncClient", return_value=fake_client):
            result = await _check_supabase_auth(timeout=2.0)
    finally:
        settings.SUPABASE_AUTH_HEALTH_URL = prev

    assert result["ok"] is False
    assert result["error"] == "ConnectionError"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_supabase_auth_check_returns_not_ok_on_5xx() -> None:
    from app.api.health import _check_supabase_auth
    from app.core.config import settings

    prev = settings.SUPABASE_AUTH_HEALTH_URL
    settings.SUPABASE_AUTH_HEALTH_URL = "https://test.supabase.co/auth/v1/health"

    fake_resp = type("R", (), {"status_code": 503})()
    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.get = AsyncMock(return_value=fake_resp)

    try:
        with patch("httpx.AsyncClient", return_value=fake_client):
            result = await _check_supabase_auth(timeout=2.0)
    finally:
        settings.SUPABASE_AUTH_HEALTH_URL = prev

    assert result["ok"] is False
    assert result["status_code"] == 503
