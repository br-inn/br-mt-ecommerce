"""Adapter Bright Data — Amazon UAE (Sprint 4 SCAFFOLD, US-1A-09-03).

MODO INFRAESTRUCTURAL: el adapter está cableado contra Bright Data Web
Scraper API (httpx + tenacity retry + circuit breaker manual + parser
testeable) pero mientras ``MT_LIVE_NETWORK != true`` cae transparente al
stub Sprint 3 (:class:`AmazonUaeStubFetcher`). Esto permite mergear la
infraestructura sin firmar Q-NEW-S3 todavía.

Cuando se habilite la red real:

1. ``MT_LIVE_NETWORK=true``
2. ``BRIGHT_DATA_API_KEY`` + ``BRIGHT_DATA_AMAZON_AE_DATASET_ID`` configurados
3. ADR-070 + Q-NEW-S3 firmados

…la primera invocación abrirá el cliente HTTP real con `Bearer` token.
Si el circuit breaker se abre (5 fallos seguidos en ventana 60s) el adapter
fallback al stub canned con ``raw_payload['degraded_mode']=true``.

Pipeline ref: ``mt-product-matching-pipeline-detail.md`` §4.2.
"""

from __future__ import annotations

import logging
import os
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.services.matching.adapters.amazon_uae_stub import AmazonUaeStubFetcher
from app.services.matching.ports import CandidateRaw, Query

logger = logging.getLogger(__name__)

CHANNEL = "amazon_uae"
_DEFAULT_BASE_URL = "https://api.brightdata.com/datasets/v3/trigger"
_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_RETRY_ATTEMPTS = 3
_DEFAULT_RETRY_MIN_WAIT_S = 1.0
_DEFAULT_RETRY_MAX_WAIT_S = 4.0
_CB_FAILURE_THRESHOLD = 5
_CB_RESET_TIMEOUT_S = 300  # 5 minutos


class _CircuitBreaker:
    """Circuit breaker mínimo (sin pybreaker) — funcional, testeable.

    Estados:
        - CLOSED: normal, requests pasan.
        - OPEN: recientes fallos; rechaza inmediatamente.
        - HALF_OPEN: probe automático tras ``reset_timeout``.

    Implementación deliberadamente simple — no thread-safe (worker async
    single-loop). Si en el futuro corremos multi-process, swappear a
    pybreaker (TODO ADR-070).
    """

    def __init__(self, failure_threshold: int = 5, reset_timeout_s: int = 60) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self._failures = 0
        self._opened_at: float | None = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if (time.monotonic() - self._opened_at) >= self.reset_timeout_s:
            # half-open probe: dejamos pasar 1 request
            self._opened_at = None
            self._failures = 0
            return False
        return True

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self.failure_threshold:
            self._opened_at = time.monotonic()

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None


def parse_bright_data_amazon(payload: dict[str, Any]) -> list[CandidateRaw]:
    """Parsea respuesta cruda Bright Data → ``list[CandidateRaw]``.

    Formato esperado (Web Scraper API Amazon dataset):
        ``{"results": [ {"asin", "title", "brand", "price", "currency",
                          "delivery", "image_urls", "specifications": {...}}, ...]}``

    Robusto ante campos faltantes — si ``asin`` o ``title`` faltan se
    omite el item. ``price`` se parsea con :class:`Decimal`; ``currency``
    se anota en ``raw_payload`` para que la capa FX lo convierta a AED
    (criterio aceptación 4 — ``price_currency_inferred``).
    """
    out: list[CandidateRaw] = []
    items = payload.get("results") or payload.get("data") or []
    if not isinstance(items, list):
        return out
    now = datetime.now(tz=UTC)
    for item in items:
        if not isinstance(item, dict):
            continue
        asin = item.get("asin") or item.get("external_id")
        title = item.get("title")
        if not asin or not title:
            continue
        price_aed: Decimal | None = None
        currency = item.get("currency")
        raw_price = item.get("price") or item.get("price_aed")
        if raw_price is not None:
            try:
                price_aed = Decimal(str(raw_price))
            except (InvalidOperation, ValueError):
                price_aed = None
        specs = item.get("specifications") or item.get("specs") or {}
        if not isinstance(specs, dict):
            specs = {}
        out.append(
            CandidateRaw(
                source=CHANNEL,
                external_id=str(asin),
                title=str(title),
                brand=item.get("brand"),
                price_aed=price_aed,
                delivery_text=item.get("delivery"),
                specs=dict(specs),
                raw_payload={
                    "currency": currency,
                    "image_urls": item.get("image_urls") or [],
                    "seller": item.get("seller"),
                    "raw": item,
                },
                fetched_at=now,
            )
        )
    return out


class BrightDataAmazonUaeFetcher:
    """Implementación real (scaffold) del :class:`FetcherPort` Amazon UAE.

    Configuración via env (lazy — no se exige tener vars en import time):

    - ``BRIGHT_DATA_API_KEY``: bearer token Web Scraper API.
    - ``BRIGHT_DATA_AMAZON_AE_DATASET_ID``: dataset ID Amazon UAE.
    - ``BRIGHT_DATA_BASE_URL`` (opcional): override del endpoint.
    - ``MT_LIVE_NETWORK``: si != true → llama directo al stub.
    """

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        circuit_breaker: _CircuitBreaker | None = None,
        stub: AmazonUaeStubFetcher | None = None,
    ) -> None:
        self._http_client = http_client
        self._owns_client = http_client is None
        self._cb = circuit_breaker or _CircuitBreaker(
            failure_threshold=_CB_FAILURE_THRESHOLD,
            reset_timeout_s=_CB_RESET_TIMEOUT_S,
        )
        self._stub = stub or AmazonUaeStubFetcher()

    @property
    def channel(self) -> str:
        return CHANNEL

    def _live_enabled(self) -> bool:
        val = os.environ.get("MT_LIVE_NETWORK", "false").strip().lower()
        return val in {"1", "true", "yes", "on"}

    def _credentials(self) -> tuple[str | None, str | None, str]:
        api_key = os.environ.get("BRIGHT_DATA_API_KEY")
        dataset_id = os.environ.get("BRIGHT_DATA_AMAZON_AE_DATASET_ID")
        base_url = os.environ.get("BRIGHT_DATA_BASE_URL", _DEFAULT_BASE_URL)
        return api_key, dataset_id, base_url

    async def _http(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_S)
        return self._http_client

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def fetch(
        self, query: Query, *, sku: str | None = None
    ) -> list[CandidateRaw]:
        # 1. Modo scaffold: si red real desactivada → stub directo.
        if not self._live_enabled():
            return await self._stub.fetch(query, sku=sku)

        # 2. Credenciales obligatorias en modo real; si faltan, fallback stub.
        api_key, dataset_id, base_url = self._credentials()
        if not api_key or not dataset_id:
            logger.warning(
                "bright_data.amazon_uae: missing credentials, falling back to stub",
            )
            return await self._stub.fetch(query, sku=sku)

        # 3. Circuit breaker.
        if self._cb.is_open():
            logger.warning("bright_data.amazon_uae: circuit_breaker_open, fallback stub")
            return self._degraded(await self._stub.fetch(query, sku=sku))

        # 4. HTTP real con retry exponencial.
        try:
            payload = await self._call_bright_data(
                api_key=api_key,
                dataset_id=dataset_id,
                base_url=base_url,
                query=query,
            )
        except (RetryError, httpx.HTTPError) as exc:
            logger.exception("bright_data.amazon_uae: fetch failed: %s", exc)
            self._cb.record_failure()
            return self._degraded(await self._stub.fetch(query, sku=sku))

        self._cb.record_success()
        return parse_bright_data_amazon(payload)

    async def _call_bright_data(
        self,
        *,
        api_key: str,
        dataset_id: str,
        base_url: str,
        query: Query,
    ) -> dict[str, Any]:
        """Una llamada HTTP envuelta en tenacity retry."""
        client = await self._http()
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        request_payload = {
            "dataset_id": dataset_id,
            "query": query.text,
            "marketplace": "amazon_ae",
            "limit": 20,
        }
        retryer = AsyncRetrying(
            stop=stop_after_attempt(_DEFAULT_RETRY_ATTEMPTS),
            wait=wait_exponential(
                multiplier=_DEFAULT_RETRY_MIN_WAIT_S,
                max=_DEFAULT_RETRY_MAX_WAIT_S,
            ),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )
        async for attempt in retryer:
            with attempt:
                resp = await client.post(base_url, json=request_payload, headers=headers)
                resp.raise_for_status()
                return resp.json()
        # unreachable; tenacity reraises
        raise RuntimeError("unreachable")

    def _degraded(self, candidates: list[CandidateRaw]) -> list[CandidateRaw]:
        """Marca los resultados como degraded (criterio 3)."""
        for c in candidates:
            c.raw_payload = {**c.raw_payload, "degraded_mode": True}
        return candidates


__all__ = [
    "BrightDataAmazonUaeFetcher",
    "_CircuitBreaker",
    "parse_bright_data_amazon",
]
