"""TradelingAdapter — fetcher de precios/listings de Tradeling (MENA B2B).

Tradeling es el marketplace B2B más relevante del Middle East (UAE).
Este adapter consulta la API oficial de Tradeling para obtener precios y
listings de competidores en el canal B2B regional.

US-F15-02-05.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

import httpx
from aiolimiter import AsyncLimiter
from tenacity import (
    AsyncRetrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.core.config import get_settings

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class TradelingAuthError(Exception):
    """HTTP 401/403 desde la API de Tradeling — credencial inválida o expirada."""


# ---------------------------------------------------------------------------
# DTO — resultado normalizado (no es el ORM CompetitorListing)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TradelingListing:
    """Listing normalizado de Tradeling.

    Equivalente funcional a CompetitorListing DTO (US-F15-02-05 AC#2).
    Se llama TradelingListing para no colisionar con el ORM CompetitorListing.
    """

    external_id: str
    title: str
    price: Decimal
    currency: str  # siempre "AED"
    brand: str
    seller_name: str
    product_url: str
    image_urls: list[str]
    source: str  # siempre "tradeling"


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class TradelingAdapter:
    """Fetcher de listings de competidores para Tradeling UAE.

    - Rate limit: 3 req/s via aiolimiter.AsyncLimiter.
    - Retry: tenacity 3 intentos, espera exponencial 2-8s en 429 y 5xx.
    - HTTP 401/403: NO retry — lanza TradelingAuthError inmediatamente.
    - Sin api_key: retorna [] con log WARNING (safe default).
    - Fallos persistentes: registra en competitor_fetch_errors (best-effort).
    """

    _API_BASE = "https://api.tradeling.com/v1"

    def __init__(self, *, api_key: str, rate_limit: float = 3.0) -> None:
        self._api_key = api_key
        self._limiter = AsyncLimiter(max_rate=rate_limit, time_period=1.0)

    async def fetch(
        self,
        *,
        product_title: str,
        category_id: str,
    ) -> list[TradelingListing]:
        """Busca listings en Tradeling UAE para un producto y categoría.

        GET /products/search?query={product_title}&category={category_id}&marketplace=UAE

        Returns:
            Lista de TradelingListing normalizados. Vacía si hay error o sin key.
        """
        if not self._api_key:
            logger.warning(
                "tradeling_adapter: api_key vacía — fetcher deshabilitado, retornando []"
            )
            return []

        url = f"{self._API_BASE}/products/search"
        params = {
            "query": product_title,
            "category": category_id,
            "marketplace": "UAE",
        }
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

        raw_items: list[dict[str, Any]] = []

        async with self._limiter:
            try:
                async for attempt in AsyncRetrying(
                    retry=retry_if_exception_type(_RetryableTradelingError),
                    stop=stop_after_attempt(3),
                    wait=wait_exponential(multiplier=2, min=2, max=8),
                ):
                    with attempt:
                        async with httpx.AsyncClient(timeout=30.0) as client:
                            resp = await client.get(url, headers=headers, params=params)

                        if resp.status_code in (401, 403):
                            raise TradelingAuthError(
                                f"Tradeling auth error: HTTP {resp.status_code}"
                            )

                        if resp.status_code == 429 or resp.status_code >= 500:
                            raise _RetryableTradelingError(
                                f"Tradeling transient error: HTTP {resp.status_code}"
                            )

                        resp.raise_for_status()
                        data = resp.json()
                        raw_items = data.get("items", data.get("results", []))

            except TradelingAuthError:
                raise  # no capturar — se propaga al caller

            except Exception as exc:
                # Incluye _RetryableTradelingError agotada (3 intentos) + errores de red
                status_code: int | None = None
                if isinstance(exc, _RetryableTradelingError):
                    # Extraer código HTTP del mensaje si está disponible
                    try:
                        status_code = int(str(exc).split("HTTP ")[-1].strip())
                    except (ValueError, IndexError):
                        pass
                await _log_fetch_error(
                    source="tradeling",
                    query=f"{product_title}:{category_id}",
                    exc=exc,
                    error_code=status_code,
                )
                return []

        return [_normalize(item) for item in raw_items if isinstance(item, dict)]


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


class TradelingFetcherFactory:
    """Factory que crea TradelingAdapter a partir de settings.

    Retorna None si TRADELING_API_KEY no está configurada.
    """

    @staticmethod
    def create() -> TradelingAdapter | None:
        settings = get_settings()
        api_key = settings.TRADELING_API_KEY.get_secret_value()
        if not api_key:
            logger.warning("TRADELING_API_KEY not set — Tradeling fetcher disabled")
            return None
        return TradelingAdapter(
            api_key=api_key,
            rate_limit=3.0,
        )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


class _RetryableTradelingError(Exception):
    """Error transitorio de Tradeling (429 / 5xx) — elegible para retry."""


def _normalize(item: dict[str, Any]) -> TradelingListing:
    """Normaliza un item raw de Tradeling a TradelingListing (AC#2)."""
    # price.amount — nunca float
    price_raw = item.get("price", {}) or {}
    price_amount: Decimal
    try:
        price_amount = Decimal(str(price_raw.get("amount", "0")))
    except Exception:
        price_amount = Decimal("0")

    # brand.name
    brand_raw = item.get("brand", {}) or {}
    brand = brand_raw.get("name", "") if isinstance(brand_raw, dict) else ""

    # seller.name
    seller_raw = item.get("seller", {}) or {}
    seller_name = seller_raw.get("name", "") if isinstance(seller_raw, dict) else ""

    # images[].url
    images_raw = item.get("images", []) or []
    image_urls = [img["url"] for img in images_raw if isinstance(img, dict) and img.get("url")]

    return TradelingListing(
        external_id=str(item.get("id", "")),
        title=str(item.get("title", item.get("name", ""))),
        price=price_amount,
        currency="AED",
        brand=brand or "",
        seller_name=seller_name or "",
        product_url=str(item.get("url", "")),
        image_urls=image_urls,
        source="tradeling",
    )


async def _log_fetch_error(
    *,
    source: str,
    query: str,
    exc: Exception,
    error_code: int | None,
) -> None:
    """Registra error en competitor_fetch_errors (best-effort, no lanza)."""
    try:
        from app.db import get_sessionmaker
        from app.db.models.comparator import CompetitorFetchError

        session_factory = get_sessionmaker()
        async with session_factory() as session, session.begin():
            session.add(
                CompetitorFetchError(
                    asin=query,  # campo requerido — usamos query como identificador
                    error_type=type(exc).__name__,
                    error_message=(
                        f"[source={source}]"
                        + (f"[error_code={error_code}]" if error_code else "")
                        + f" {str(exc)[:400]}"
                    )[:500],
                )
            )
    except Exception:
        logger.warning("tradeling_adapter: no se pudo registrar error en competitor_fetch_errors")


__all__ = [
    "TradelingAdapter",
    "TradelingAuthError",
    "TradelingFetcherFactory",
    "TradelingListing",
]
