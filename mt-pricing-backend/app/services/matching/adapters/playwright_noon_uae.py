"""Adapter Playwright self-host — Noon UAE (Sprint 4 SCAFFOLD, US-1A-09-04).

MODO INFRAESTRUCTURAL: el adapter expone el contrato real (browser
context async, parser HTML separado, retry, circuit breaker) pero
mientras ``MT_LIVE_NETWORK != true`` cae al stub Sprint 3 — y NO importa
``playwright`` (lib aún no añadida a dependencies). El import del browser
es lazy para que los tests unitarios sin browser instalado no rompan.

Cuando se habilite la red real:
1. ``pip install playwright && playwright install chromium``
2. ``MT_LIVE_NETWORK=true`` y ``PLAYWRIGHT_NOON_UAE_BASE_URL`` configurada
3. ADR-071 firmado.

Pipeline ref: ``mt-product-matching-pipeline-detail.md`` §4.1.
"""

from __future__ import annotations

import contextlib
import logging
import os
import time
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any, Protocol

from app.services.matching.adapters.noon_uae_stub import NoonUaeStubFetcher
from app.services.matching.ports import CandidateRaw, Query

logger = logging.getLogger(__name__)

CHANNEL = "noon_uae"
_DEFAULT_BASE_URL = "https://www.noon.com/uae-en/search"
_DEFAULT_TIMEOUT_S = 30
_CB_FAILURE_THRESHOLD = 3  # Playwright es más caro: abrir antes
_CB_RESET_TIMEOUT_S = 600


class _CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, reset_timeout_s: int = 600) -> None:
        self.failure_threshold = failure_threshold
        self.reset_timeout_s = reset_timeout_s
        self._failures = 0
        self._opened_at: float | None = None

    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if (time.monotonic() - self._opened_at) >= self.reset_timeout_s:
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


class _BrowserContext(Protocol):
    """Contrato mínimo del browser context (testeable sin Playwright real).

    Los tests inyectan un fake con ``goto`` + ``content`` (HTML string).
    En producción, se reemplaza por
    ``await browser.new_context().new_page()``.
    """

    async def goto(self, url: str) -> None: ...

    async def content(self) -> str: ...

    async def close(self) -> None: ...


def parse_noon_html(html: str) -> list[dict[str, Any]]:
    """Parser HTML de Noon — extracción regex-based (lightweight).

    Implementación deliberadamente naive para Sprint 4 scaffold: cuando
    se active red real, se cambia por ``selectolax`` o ``BeautifulSoup``
    ya en el pyproject (TODO: añadir lib). El parser se aísla aquí para
    poder testearlo con HTML capturado (``tests/fixtures/noon_uae/*.html``).
    """
    import re

    items: list[dict[str, Any]] = []
    # Cada producto Noon viene en un bloque ``data-qa="product-block"``
    blocks = re.findall(
        r'data-qa="product-block"[^>]*data-noonid="([^"]+)"[^>]*>(.+?)</article>',
        html,
        flags=re.DOTALL,
    )
    for noon_id, body in blocks:
        title_match = re.search(r'class="productTitle"[^>]*>([^<]+)<', body)
        price_match = re.search(r'class="priceNow"[^>]*>([\d.,]+)\s*AED', body)
        brand_match = re.search(r'class="brand"[^>]*>([^<]+)<', body)
        ar_title_match = re.search(r'lang="ar"[^>]*>([^<]+)<', body)
        items.append(
            {
                "noon_id": noon_id,
                "title": (title_match.group(1).strip() if title_match else ""),
                "title_ar": (ar_title_match.group(1).strip() if ar_title_match else None),
                "brand": (brand_match.group(1).strip() if brand_match else None),
                "price_aed": (price_match.group(1).replace(",", "") if price_match else None),
            }
        )
    return items


def map_noon_to_candidate(items: list[dict[str, Any]]) -> list[CandidateRaw]:
    """Convierte items parseados → :class:`CandidateRaw`."""
    out: list[CandidateRaw] = []
    now = datetime.now(tz=UTC)
    for it in items:
        noon_id = it.get("noon_id")
        title = it.get("title")
        if not noon_id or not title:
            continue
        price_aed: Decimal | None = None
        if it.get("price_aed"):
            try:
                price_aed = Decimal(str(it["price_aed"]))
            except (InvalidOperation, ValueError):
                price_aed = None
        specs: dict[str, Any] = {}
        if it.get("title_ar"):
            specs["arabic_title"] = it["title_ar"]
        out.append(
            CandidateRaw(
                source=CHANNEL,
                external_id=str(noon_id),
                title=str(title),
                brand=it.get("brand"),
                price_aed=price_aed,
                delivery_text=None,
                specs=specs,
                raw_payload={"raw": it},
                fetched_at=now,
            )
        )
    return out


class PlaywrightNoonUaeFetcher:
    """Implementación scaffold del :class:`FetcherPort` Noon UAE.

    Diseñado para que los tests inyecten ``browser_factory`` (callable
    que devuelve un ``_BrowserContext``). En prod, ``browser_factory`` se
    reemplaza por una closure que abre Playwright headless.
    """

    def __init__(
        self,
        *,
        browser_factory: Any | None = None,
        circuit_breaker: _CircuitBreaker | None = None,
        stub: NoonUaeStubFetcher | None = None,
    ) -> None:
        self._browser_factory = browser_factory  # async callable -> _BrowserContext
        self._cb = circuit_breaker or _CircuitBreaker(
            failure_threshold=_CB_FAILURE_THRESHOLD,
            reset_timeout_s=_CB_RESET_TIMEOUT_S,
        )
        self._stub = stub or NoonUaeStubFetcher()

    @property
    def channel(self) -> str:
        return CHANNEL

    def _live_enabled(self) -> bool:
        val = os.environ.get("MT_LIVE_NETWORK", "false").strip().lower()
        return val in {"1", "true", "yes", "on"}

    async def fetch(self, query: Query, *, sku: str | None = None) -> list[CandidateRaw]:
        if not self._live_enabled():
            return await self._stub.fetch(query, sku=sku)

        if self._browser_factory is None:
            logger.warning("playwright.noon_uae: no browser_factory injected, fallback stub")
            return await self._stub.fetch(query, sku=sku)

        if self._cb.is_open():
            logger.warning("playwright.noon_uae: circuit open, fallback stub")
            return self._degraded(await self._stub.fetch(query, sku=sku))

        base_url = os.environ.get("PLAYWRIGHT_NOON_UAE_BASE_URL", _DEFAULT_BASE_URL)
        url = f"{base_url}?q={query.text}"

        ctx: _BrowserContext | None = None
        try:
            ctx = await self._browser_factory()
            await ctx.goto(url)
            html = await ctx.content()
        except Exception as exc:
            logger.exception("playwright.noon_uae: navigation failed: %s", exc)
            self._cb.record_failure()
            return self._degraded(await self._stub.fetch(query, sku=sku))
        finally:
            if ctx is not None:
                with contextlib.suppress(Exception):
                    await ctx.close()

        self._cb.record_success()
        items = parse_noon_html(html)
        return map_noon_to_candidate(items)

    def _degraded(self, candidates: list[CandidateRaw]) -> list[CandidateRaw]:
        for c in candidates:
            c.raw_payload = {**c.raw_payload, "degraded_mode": True}
        return candidates


__all__ = [
    "PlaywrightNoonUaeFetcher",
    "_CircuitBreaker",
    "map_noon_to_candidate",
    "parse_noon_html",
]
