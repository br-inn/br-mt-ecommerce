"""Unit tests para JWT helpers — claim extraction + JWKS cache + decode_with_jwks.

Cobertura:
- `extract_role_claim` lee `app_metadata.role` (preferente) y fallback a `user_metadata.role`.
- `extract_role_claim` retorna None si ausente o tipo inválido.
- `JWKSCache.get()` hace fetch on miss y caches por kid.
- `JWKSCache.is_fresh` respeta el TTL.
- `JWKSCache.force_refresh()` re-fetcha.
- `decode_with_jwks` rechaza tokens sin `kid`.
- `_decode_jwt` HS256 válido → payload.
- `_decode_jwt` HS256 expirado → 401.
"""

from __future__ import annotations

import os
import time
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from jose import JWTError, jwt

# Forzar secret antes de importar config singleton.
os.environ.setdefault("SUPABASE_JWT_SECRET", "test-jwt-secret-deterministic-32chars!")
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")

JWT_SECRET = "test-jwt-secret-deterministic-32chars!"


# ===========================================================================
# extract_role_claim
# ===========================================================================
@pytest.mark.unit
def test_extract_role_from_app_metadata() -> None:
    from app.api.deps import extract_role_claim

    payload = {"sub": "u1", "app_metadata": {"role": "comercial"}}
    assert extract_role_claim(payload) == "comercial"


@pytest.mark.unit
def test_extract_role_falls_back_to_user_metadata() -> None:
    from app.api.deps import extract_role_claim

    payload = {"sub": "u1", "user_metadata": {"role": "ti"}}
    assert extract_role_claim(payload) == "ti"


@pytest.mark.unit
def test_extract_role_missing_returns_none() -> None:
    from app.api.deps import extract_role_claim

    assert extract_role_claim({"sub": "u1"}) is None
    assert extract_role_claim({"sub": "u1", "app_metadata": {}}) is None
    assert extract_role_claim({"sub": "u1", "app_metadata": {"role": ""}}) is None


@pytest.mark.unit
def test_extract_role_app_metadata_not_dict_returns_none() -> None:
    from app.api.deps import extract_role_claim

    assert extract_role_claim({"sub": "u1", "app_metadata": "garbage"}) is None


# ===========================================================================
# JWKSCache
# ===========================================================================
@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwks_cache_fetches_on_miss() -> None:
    from app.core.jwks import JWKSCache

    cache = JWKSCache(jwks_url="https://example/jwks", ttl_seconds=3600)
    fake_keys = {"keys": [{"kid": "k1", "kty": "RSA", "alg": "RS256", "n": "x", "e": "AQAB"}]}

    fake_resp = type(
        "R", (), {"json": lambda self: fake_keys, "raise_for_status": lambda self: None}
    )()

    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.get = AsyncMock(return_value=fake_resp)

    with patch("app.core.jwks.httpx.AsyncClient", return_value=fake_client):
        jwk = await cache.get("k1")

    assert jwk is not None
    assert jwk["kid"] == "k1"
    assert cache.is_fresh
    fake_client.get.assert_awaited_once_with("https://example/jwks")


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwks_cache_hit_does_not_refetch() -> None:
    """Segundo .get() para el mismo kid mientras está fresh NO debe refetch."""
    from app.core.jwks import JWKSCache

    cache = JWKSCache(jwks_url="https://example/jwks", ttl_seconds=3600)
    fake_keys = {"keys": [{"kid": "k1", "kty": "RSA"}]}
    fake_resp = type(
        "R", (), {"json": lambda self: fake_keys, "raise_for_status": lambda self: None}
    )()

    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.get = AsyncMock(return_value=fake_resp)

    with patch("app.core.jwks.httpx.AsyncClient", return_value=fake_client):
        await cache.get("k1")
        await cache.get("k1")
        await cache.get("k1")

    # Sólo 1 fetch para los 3 .get() — cache hit.
    assert fake_client.get.await_count == 1


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwks_cache_expired_refetches() -> None:
    from app.core.jwks import JWKSCache

    cache = JWKSCache(jwks_url="https://example/jwks", ttl_seconds=0)  # TTL=0 → siempre stale
    fake_keys = {"keys": [{"kid": "k1", "kty": "RSA"}]}
    fake_resp = type(
        "R", (), {"json": lambda self: fake_keys, "raise_for_status": lambda self: None}
    )()

    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.get = AsyncMock(return_value=fake_resp)

    with patch("app.core.jwks.httpx.AsyncClient", return_value=fake_client):
        await cache.get("k1")
        time.sleep(0.01)
        await cache.get("k1")

    # TTL=0 → cada .get() refetcha.
    assert fake_client.get.await_count == 2


@pytest.mark.unit
@pytest.mark.asyncio
async def test_jwks_cache_force_refresh_resets() -> None:
    from app.core.jwks import JWKSCache

    cache = JWKSCache(jwks_url="https://example/jwks", ttl_seconds=3600)
    fake_keys = {"keys": [{"kid": "k1", "kty": "RSA"}]}
    fake_resp = type(
        "R", (), {"json": lambda self: fake_keys, "raise_for_status": lambda self: None}
    )()

    fake_client = AsyncMock()
    fake_client.__aenter__ = AsyncMock(return_value=fake_client)
    fake_client.__aexit__ = AsyncMock(return_value=False)
    fake_client.get = AsyncMock(return_value=fake_resp)

    with patch("app.core.jwks.httpx.AsyncClient", return_value=fake_client):
        await cache.get("k1")
        await cache.force_refresh()

    assert fake_client.get.await_count == 2


# ===========================================================================
# decode_with_jwks
# ===========================================================================
@pytest.mark.unit
@pytest.mark.asyncio
async def test_decode_with_jwks_rejects_token_without_kid() -> None:
    from app.core.jwks import decode_with_jwks

    # Token sin `kid` en el header — usamos HS256 con secret cualquiera.
    token = jwt.encode({"sub": "u1", "aud": "authenticated"}, "secret", algorithm="HS256")

    with pytest.raises(JWTError, match="kid"):
        await decode_with_jwks(token, audience="authenticated")


# ===========================================================================
# _decode_jwt (HS256 path — default)
# ===========================================================================
@pytest.mark.unit
@pytest.mark.asyncio
async def test_decode_jwt_hs256_valid_returns_payload(monkeypatch) -> None:
    """HS256 happy path. Refuerza el secret en el singleton `settings` por si
    otro test cargó settings antes con un valor distinto (orden-independencia).
    """
    from pydantic import SecretStr

    from app.api import deps as deps_module
    from app.api.deps import _decode_jwt

    monkeypatch.setattr(
        deps_module.settings,
        "SUPABASE_JWT_SECRET",
        SecretStr(JWT_SECRET),
        raising=False,
    )
    monkeypatch.setattr(
        deps_module.settings,
        "SUPABASE_JWT_VERIFICATION_MODE",
        "hs256",
        raising=False,
    )

    now = int(time.time())
    payload = {
        "sub": "user-1",
        "aud": "authenticated",
        "email": "alice@mt.ae",
        "iat": now,
        "exp": now + 3600,
        "app_metadata": {"role": "comercial"},
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    decoded = await _decode_jwt(token)
    assert decoded["sub"] == "user-1"
    assert decoded["app_metadata"]["role"] == "comercial"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decode_jwt_hs256_expired_raises_401() -> None:
    from app.api.deps import _decode_jwt

    now = int(time.time())
    payload = {
        "sub": "user-1",
        "aud": "authenticated",
        "iat": now - 7200,
        "exp": now - 3600,  # expirado hace 1h
    }
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")

    with pytest.raises(HTTPException) as exc:
        await _decode_jwt(token)
    assert exc.value.status_code == 401


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decode_jwt_hs256_wrong_signature_raises_401() -> None:
    from app.api.deps import _decode_jwt

    now = int(time.time())
    token = jwt.encode(
        {"sub": "u", "aud": "authenticated", "iat": now, "exp": now + 60},
        "wrong-secret-not-the-real-one!",
        algorithm="HS256",
    )

    with pytest.raises(HTTPException) as exc:
        await _decode_jwt(token)
    assert exc.value.status_code == 401


@pytest.mark.unit
@pytest.mark.asyncio
async def test_decode_jwt_jwks_mode_invokes_jwks_path() -> None:
    """Si VERIFICATION_MODE='jwks', se delega a `decode_with_jwks`."""

    from app.api.deps import _decode_jwt
    from app.core.config import settings

    # Override transitorio del modo.
    prev_mode = settings.SUPABASE_JWT_VERIFICATION_MODE
    settings.SUPABASE_JWT_VERIFICATION_MODE = "jwks"
    try:
        fake_payload: dict[str, Any] = {"sub": "u", "exp": 9999999999}
        with patch(
            "app.core.jwks.decode_with_jwks",
            new=AsyncMock(return_value=fake_payload),
        ) as m:
            result = await _decode_jwt("fake.token.value")
        assert result == fake_payload
        m.assert_awaited_once()
    finally:
        settings.SUPABASE_JWT_VERIFICATION_MODE = prev_mode
