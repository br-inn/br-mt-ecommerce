"""AmazonSPApiFetcherAdapter — obtiene precios de competidores en Amazon UAE.

Distinto de AmazonSPApiAdapter en channel_mirror (ese PUBLICA precios).
Este OBTIENE precios de competidores para el comparador.

Fallback automático a AmazonSPFetcherStub cuando:
- settings.MT_LIVE_NETWORK != "true"
- Faltan credenciales SP_API_*
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import settings
from app.services.comparator.fetchers import CompetitorPrice, FetcherPort
from app.services.comparator.fetchers.amazon_sp_fetcher_stub import AmazonSPFetcherStub

logger = logging.getLogger(__name__)

_MARKETPLACE_ID = "A2VIGQ35RCS4UG"  # Amazon.ae UAE
_SP_API_BASE = "https://sellingpartnerapi-eu.amazon.com"
_LWA_TOKEN_URL = "https://api.amazon.com/auth/o2/token"
_LWA_TOKEN_TTL_S = 3500
_RATE_LIMITER = AsyncLimiter(max_rate=2, time_period=1.0)


class AmazonSPApiFetcherAdapter:
    """Adapter real SP-API para fetching de precios de competidores.

    Cachea el LWA token en memoria (TTL 3500s).
    Rate limit: 2 req/s via AsyncLimiter.
    Fallback automático al stub si MT_LIVE_NETWORK != "true" o faltan credenciales.
    """

    def __init__(self) -> None:
        self._token: str | None = None
        self._token_expires_at: float = 0.0

    def _has_credentials(self) -> bool:
        return bool(
            settings.SP_API_REFRESH_TOKEN
            and settings.SP_API_LWA_CLIENT_ID
            and settings.SP_API_LWA_CLIENT_SECRET.get_secret_value()
        )

    async def _refresh_token(self) -> str:
        """LWA OAuth2 token refresh."""
        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.post(
                _LWA_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": settings.SP_API_REFRESH_TOKEN,
                    "client_id": settings.SP_API_LWA_CLIENT_ID,
                    "client_secret": settings.SP_API_LWA_CLIENT_SECRET.get_secret_value(),
                },
            )
            resp.raise_for_status()
            data = resp.json()
            self._token = data["access_token"]
            self._token_expires_at = time.time() + _LWA_TOKEN_TTL_S
            return self._token

    async def _get_token(self) -> str:
        if self._token is None or time.time() >= self._token_expires_at:
            return await self._refresh_token()
        return self._token

    async def fetch_competitor_price(self, asin: str) -> CompetitorPrice:
        if settings.MT_LIVE_NETWORK != "true" or not self._has_credentials():
            logger.debug(
                "amazon_sp_fetcher: fallback a stub (live_network=%s)",
                settings.MT_LIVE_NETWORK,
            )
            stub = AmazonSPFetcherStub()
            return await stub.fetch_competitor_price(asin)

        async with _RATE_LIMITER:
            data: dict = {}
            try:
                async for attempt in AsyncRetrying(
                    retry=retry_if_exception_type(httpx.HTTPError),
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=1, min=2, max=30),
                ):
                    with attempt:
                        token = await self._get_token()
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(
                                f"{_SP_API_BASE}/catalog/2022-04-01/items/{asin}",
                                headers={
                                    "Authorization": f"Bearer {token}",
                                    "x-amz-access-token": token,
                                    "Content-Type": "application/json",
                                },
                                params={"marketplaceIds": _MARKETPLACE_ID},
                            )
                            resp.raise_for_status()
                            data = resp.json()
            except Exception as exc:
                await _log_fetch_error(asin, exc)
                stub = AmazonSPFetcherStub()
                return await stub.fetch_competitor_price(asin)

        price_aed = _extract_price(data)
        return CompetitorPrice(
            asin=asin,
            price_aed=price_aed,
            currency="AED",
            marketplace_id=_MARKETPLACE_ID,
            fetched_at=datetime.now(UTC),
            source="amazon_sp_api",
        )

    async def health_check(self) -> dict[str, Any]:
        live = settings.MT_LIVE_NETWORK == "true" and self._has_credentials()
        return {
            "healthy": True,
            "source": "amazon_sp_api" if live else "stub_fallback",
            "live_network": live,
        }


def _extract_price(payload: dict) -> float:
    """Extrae precio AED del payload getCatalogItem."""
    try:
        summaries = payload.get("summaries", [{}])
        for s in summaries:
            if s.get("marketplaceId") == _MARKETPLACE_ID:
                # Precio puede estar en diferentes campos según endpoint
                return float(s.get("listPrice", {}).get("amount", 0.0))
    except (KeyError, TypeError, ValueError):
        pass
    return 0.0


async def _log_fetch_error(asin: str, exc: Exception) -> None:
    """Registra error en competitor_fetch_errors (best-effort)."""
    try:
        from app.db import get_sessionmaker
        from app.db.models.comparator import CompetitorFetchError

        session_factory = get_sessionmaker()
        async with session_factory() as session, session.begin():
            session.add(
                CompetitorFetchError(
                    asin=asin,
                    error_type=type(exc).__name__,
                    error_message=str(exc)[:500],
                )
            )
    except Exception:
        logger.warning("amazon_sp_fetcher: no se pudo registrar error en DB")


def get_fetcher() -> FetcherPort:
    """Factory: retorna adapter real o stub según settings."""
    if settings.MT_LIVE_NETWORK == "true":
        return AmazonSPApiFetcherAdapter()
    return AmazonSPFetcherStub()


__all__ = ["AmazonSPApiFetcherAdapter", "get_fetcher"]
