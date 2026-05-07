"""JWKS fetch + in-memory cache para validar JWTs RS256/ES256 de Supabase.

Por defecto Supabase emite access_tokens HS256 firmados con `SUPABASE_JWT_SECRET`,
y `app.api.deps._decode_jwt` los valida con secret simétrico. Sin embargo el
backlog (US-1A-01-05) pide explícitamente un path JWKS con cache TTL 1 h para
proyectos Supabase configurados con asymmetric signing keys (modo "asymmetric"
de la nueva Auth API).

Este módulo expone:

- ``get_jwk(kid)`` — devuelve el JWK (dict) por `kid`, refrescando JWKS si no
  existe o si el TTL expiró.
- ``decode_with_jwks(token, *, audience)`` — verifica el JWT contra el JWKS,
  refrescando una sola vez si el `kid` cambió (rotación de claves).

Diseñado para ser **no-blocking** y thread-safe — usamos `asyncio.Lock` para
proteger la carga concurrent y `httpx.AsyncClient` para el fetch HTTP.

Uso (opt-in vía `settings.SUPABASE_JWT_VERIFICATION_MODE == "jwks"`)::

    from app.core.jwks import decode_with_jwks
    payload = await decode_with_jwks(token, audience="authenticated")
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
from jose import jwt
from jose.exceptions import JWTError

from app.core.config import settings

__all__ = ["JWKSCache", "decode_with_jwks", "get_jwks_cache"]


class JWKSCache:
    """Cache TTL in-memory de un JWKS — refresh on miss + on expiry."""

    def __init__(self, *, jwks_url: str, ttl_seconds: int = 3600, http_timeout: float = 5.0) -> None:
        self._jwks_url = jwks_url
        self._ttl = ttl_seconds
        self._timeout = http_timeout
        self._keys_by_kid: dict[str, dict[str, Any]] = {}
        self._fetched_at: float = 0.0
        self._lock = asyncio.Lock()

    @property
    def ttl_seconds(self) -> int:
        return self._ttl

    @property
    def is_fresh(self) -> bool:
        return bool(self._keys_by_kid) and (time.monotonic() - self._fetched_at) < self._ttl

    async def get(self, kid: str) -> dict[str, Any] | None:
        """Devuelve la JWK por `kid`, refrescando si caducó o si no existe."""
        if not self.is_fresh or kid not in self._keys_by_kid:
            await self._refresh()
        return self._keys_by_kid.get(kid)

    async def force_refresh(self) -> None:
        """Útil para rotación detectada (kid no encontrado)."""
        async with self._lock:
            await self._fetch_locked()

    async def _refresh(self) -> None:
        async with self._lock:
            # Doble-check: otro task pudo refrescar entre el `is_fresh` check
            # y la adquisición del lock.
            if self.is_fresh:
                return
            await self._fetch_locked()

    async def _fetch_locked(self) -> None:
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            resp = await client.get(self._jwks_url)
            resp.raise_for_status()
            payload = resp.json()
        keys = payload.get("keys") or []
        self._keys_by_kid = {k["kid"]: k for k in keys if "kid" in k}
        self._fetched_at = time.monotonic()


_cache: JWKSCache | None = None


def get_jwks_cache() -> JWKSCache:
    """Singleton — instanciado lazy para que tests puedan parchear `settings`."""
    global _cache
    if _cache is None:
        url = settings.SUPABASE_JWKS_URL or f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _cache = JWKSCache(jwks_url=url, ttl_seconds=settings.SUPABASE_JWKS_CACHE_TTL_SECONDS)
    return _cache


def reset_jwks_cache() -> None:
    """Helper para tests."""
    global _cache
    _cache = None


async def decode_with_jwks(
    token: str,
    *,
    audience: str = "authenticated",
    issuer: str | None = None,
) -> dict[str, Any]:
    """Verifica un JWT firma asimétrica contra el JWKS de Supabase.

    Lanza ``jose.JWTError`` (o sub-clases) si el token es inválido — el caller
    en `app.api.deps` lo traduce a 401.
    """
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise JWTError(f"invalid-jwt-header: {exc}") from exc

    kid = unverified_header.get("kid")
    if not kid:
        raise JWTError("jwt missing 'kid' in header")

    cache = get_jwks_cache()
    jwk = await cache.get(kid)
    if jwk is None:
        # Posible rotación — fuerza un refresh y reintenta UNA vez.
        await cache.force_refresh()
        jwk = await cache.get(kid)
    if jwk is None:
        raise JWTError(f"unknown jwt kid={kid}")

    alg = unverified_header.get("alg") or jwk.get("alg") or "RS256"

    options = {"require": ["exp", "sub"]}
    decode_kwargs: dict[str, Any] = {
        "algorithms": [alg],
        "audience": audience,
        "options": options,
    }
    if issuer:
        decode_kwargs["issuer"] = issuer

    return jwt.decode(token, jwk, **decode_kwargs)
