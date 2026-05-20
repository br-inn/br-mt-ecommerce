"""Fetcher genérico data-driven — ejecuta la receta de un ScraperSource.

Implementa el FetcherPort existente. F1 soporta el modo de fetch 'static'
(curl_cffi). Los modos 'headless'/'stealth' se implementan en una fase posterior:
construir un fetcher para esos modos lanza NotImplementedError.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Awaitable, Callable

from app.services.matching.ports import CandidateRaw, Query
from app.services.scraper.recipe_extractor import extract_records

HtmlFetcher = Callable[[str], Awaitable[str]]

_CANONICAL_FIELDS = {"external_id", "title", "brand", "price_aed", "delivery_text"}
_BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AE,en;q=0.9,ar;q=0.8",
}


async def _curl_cffi_fetch(url: str) -> str:
    from curl_cffi.requests import AsyncSession

    impersonate = os.environ.get("SCRAPER_IMPERSONATE", "chrome124")
    timeout = int(os.environ.get("SCRAPER_TIMEOUT", "30"))
    async with AsyncSession(
        impersonate=impersonate, headers=_BASE_HEADERS, timeout=timeout
    ) as session:
        resp = await session.get(url)
        return resp.text


class GenericConfigurableFetcher:
    """FetcherPort que ejecuta una receta data-driven contra un sitio configurado."""

    def __init__(
        self,
        source: Any,
        recipe: dict[str, Any],
        *,
        html_fetcher: HtmlFetcher | None = None,
    ) -> None:
        self._source = source
        self._recipe = recipe
        if html_fetcher is not None:
            self._html_fetcher: HtmlFetcher = html_fetcher
        elif source.fetch_mode == "static":
            self._html_fetcher = _curl_cffi_fetch
        else:
            raise NotImplementedError(
                f"fetch_mode {source.fetch_mode!r} no soportado en F1 — solo 'static'"
            )

    @property
    def channel(self) -> str:
        return self._source.slug

    def _build_url(self, query: Query) -> str:
        templates = self._recipe.get("url_templates", {})
        template = templates.get("search") or templates.get("list")
        if not template:
            raise ValueError("recipe.url_templates no define 'search' ni 'list'")
        return template.replace("{query}", query.text)

    async def fetch(self, query: Query, *, sku: str | None = None) -> list[CandidateRaw]:
        url = self._build_url(query)
        html = await self._html_fetcher(url)
        records = extract_records(html, self._recipe)
        out: list[CandidateRaw] = []
        for record in records:
            if not record.get("external_id") or not record.get("title"):
                continue
            out.append(self._to_candidate(record))
        return out

    def _to_candidate(self, record: dict[str, Any]) -> CandidateRaw:
        price_aed: Decimal | None = None
        price_raw = record.get("price_aed")
        if price_raw is not None:
            try:
                price_aed = Decimal(str(price_raw))
            except (InvalidOperation, ValueError):
                price_aed = None
        specs = {
            k: v
            for k, v in record.items()
            if k not in _CANONICAL_FIELDS and v is not None
        }
        return CandidateRaw(
            source=self.channel,
            external_id=str(record["external_id"]),
            title=str(record["title"]),
            brand=record.get("brand"),
            price_aed=price_aed,
            delivery_text=record.get("delivery_text"),
            specs=specs,
            raw_payload={"recipe_source": self.channel, "extracted": record},
            fetched_at=datetime.now(tz=timezone.utc),
        )
