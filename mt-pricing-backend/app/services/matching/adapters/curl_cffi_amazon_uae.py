"""Tier 1 live scraper — Amazon UAE via curl_cffi browser impersonation.

Tier 1 live scraper for SERP + PDP scraping when the feature
flag ``live_scraper_amazon_uae`` is enabled (see adapter_registry.py).

Architecture:
- Uses curl_cffi to impersonate a real browser (Chrome 124 by default) so
  Amazon's bot-detection does not challenge us on most requests.
- Fetches the SERP page, extracts top ASINs, then fetches each PDP to collect
  structured specs. Both steps use the extractors in
  ``app.services.matching.extractors``.
- If Amazon returns 403 or redirects to the CAPTCHA solver page, raises
  ``ScraperBlockedError`` so the adapter_registry can fall back to the stub.

Env vars (all optional):
    SCRAPER_PROXY_URL      HTTP/SOCKS5 proxy URL (e.g. "http://user:pass@host:port")
    SCRAPER_IMPERSONATE    curl_cffi browser target (default "chrome124")
    SCRAPER_TIMEOUT        Request timeout in seconds (default 30)
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import quote_plus
from uuid import UUID

from curl_cffi.requests import AsyncSession

from app.services.matching.extractors.pdp_extractor import (
    _extract_specs_from_title,
    extract_pdp_specs,
)
from app.services.matching.extractors.serp_extractor import extract_top_results
from app.services.matching.ports import CandidateRaw, Query
from app.services.matching.scraper_errors import ScraperBlockedError

logger = logging.getLogger(__name__)

_AMAZON_AE_BASE = "https://www.amazon.ae"
_CAPTCHA_PATH = "/errors/validatecaptcha"

_DEFAULT_IMPERSONATE = "chrome124"
_DEFAULT_TIMEOUT = 30

# Realistic browser headers for Amazon UAE (English storefront).
_BASE_HEADERS: dict[str, str] = {
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "en-AE,en;q=0.9,ar;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Upgrade-Insecure-Requests": "1",
}

# Re-export so callers that imported ScraperBlockedError from this module
# directly (pre-refactor) continue to work without changes.
__all__ = ["CurlCffiAmazonUaeFetcher", "ScraperBlockedError"]


class CurlCffiAmazonUaeFetcher:
    """Tier 1 live fetcher for Amazon UAE using curl_cffi browser impersonation.

    Implements :class:`app.services.matching.ports.FetcherPort`.
    """

    channel = "amazon_uae"

    def __init__(
        self,
        brand_id: UUID | None = None,
        brand_attribute_map: dict | None = None,
    ) -> None:
        # Impersonation pool — rotate randomly on each session to avoid fingerprinting.
        # SCRAPER_IMPERSONATE_POOL overrides; falls back to legacy SCRAPER_IMPERSONATE
        # (single value) and then to the built-in default pool.
        _pool_str = os.environ.get("SCRAPER_IMPERSONATE_POOL", "")
        if _pool_str:
            self._impersonate_pool: list[str] = [s.strip() for s in _pool_str.split(",") if s.strip()]
        else:
            _single = os.environ.get("SCRAPER_IMPERSONATE", "")
            self._impersonate_pool = [_single] if _single else ["chrome120", "chrome124", "chrome126"]
        self._timeout: int = int(os.environ.get("SCRAPER_TIMEOUT", _DEFAULT_TIMEOUT))
        self._proxy: str | None = os.environ.get("SCRAPER_PROXY_URL") or None
        self._brand_id: UUID | None = brand_id
        self._brand_attribute_map: dict = brand_attribute_map or {}

    async def fetch(self, query: Query, *, sku: str | None = None) -> list[CandidateRaw]:
        """Fetch live candidates from Amazon UAE for the given query.

        Steps:
            1. GET SERP for ``query.text`` and extract top ASINs.
            2. GET each PDP to collect structured specs.
            3. Map results to :class:`CandidateRaw`.

        Raises:
            ScraperBlockedError: if Amazon returns 403 or redirects to CAPTCHA.
        """
        now = datetime.now(tz=timezone.utc)

        async with self._make_session() as session:
            serp_results = await self._fetch_serp(session, query)

            candidates: list[CandidateRaw] = []
            for item in serp_results:
                asin = item.get("asin")
                if not asin:
                    continue

                # Polite delay between PDP requests.
                await asyncio.sleep(random.uniform(1.5, 4.0))

                pdp_specs = await self._fetch_pdp(session, asin)

                price_raw = item.get("price_aed")
                price_aed: Decimal | None = (
                    price_raw if isinstance(price_raw, Decimal) else None
                )

                title = str(item.get("title") or pdp_specs.get("title_pdp") or "")

                # Build specs from PDP; fall back to regex extraction from the
                # SERP title when Amazon served a bot-challenge page (empty PDP).
                _ADMIN_KEYS = {"title_pdp", "canonical_url", "raw_pairs", "asin",
                               "manufacturer_part_number", "model_number"}
                specs = {k: v for k, v in pdp_specs.items() if k not in _ADMIN_KEYS}

                # Apply brand-specific attribute mapping if available (US-SCR-05-01).
                # raw_pairs from the PDP extractor contain the unprocessed Amazon table.
                _raw_pairs_for_mapping = pdp_specs.get("raw_pairs") or []
                if _raw_pairs_for_mapping and self._brand_id:
                    try:
                        from app.services.scraper.brand_extractor_service import (
                            BrandExtractorService, apply_mapping,
                        )
                        _mapped = apply_mapping(self._brand_attribute_map, _raw_pairs_for_mapping)
                        if _mapped:
                            specs.update(_mapped)
                    except Exception:  # noqa: BLE001
                        pass  # fallback to generic extraction silently

                if not specs and title:
                    raw_pairs: list[dict] = []
                    _extract_specs_from_title(title, raw_pairs)
                    from app.services.matching.extractors.pdp_extractor import (
                        LABEL_TO_KEY, _normalize_label,
                    )
                    for pair in raw_pairs:
                        key = LABEL_TO_KEY.get(_normalize_label(pair["label"]))
                        if key:
                            specs.setdefault(key, pair["value"])

                # Also extract price from PDP when the SERP didn't show one.
                if price_aed is None:
                    pdp_price_raw = pdp_specs.get("price_aed")
                    if pdp_price_raw:
                        try:
                            price_aed = Decimal(str(pdp_price_raw))
                        except Exception:  # noqa: BLE001
                            pass

                candidates.append(
                    CandidateRaw(
                        source=self.channel,
                        external_id=asin,
                        title=title,
                        brand=str(pdp_specs.get("brand_name") or "") or None,
                        price_aed=price_aed,
                        delivery_text=None,
                        specs=specs,
                        raw_payload={
                            "asin": asin,
                            "image_url": item.get("image_url", ""),
                            "url": item.get("url", ""),
                            "query_text": query.text,
                            "query_type": query.type,
                            # Description stored for LLM spec enrichment (Capa 1).
                            "description_text": pdp_specs.get("description_text", ""),
                        },
                        fetched_at=now,
                    )
                )

        return candidates

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _make_session(self) -> AsyncSession:
        impersonate = random.choice(self._impersonate_pool)
        logger.debug("scraper.session.impersonate", extra={"target": impersonate})
        kwargs: dict = {
            "impersonate": impersonate,
            "headers": _BASE_HEADERS,
            "timeout": self._timeout,
        }
        if self._proxy:
            kwargs["proxies"] = {"http": self._proxy, "https": self._proxy}
        return AsyncSession(**kwargs)

    async def _fetch_serp(self, session: AsyncSession, query: Query) -> list[dict]:
        url = f"{_AMAZON_AE_BASE}/s?k={quote_plus(query.text)}"
        if query.dept:
            url += f"&i={query.dept}"
        if query.category_node:
            url += f"&rh=n:{query.category_node}"
        url += "&language=en_AE"

        logger.debug("scraper.serp.fetch", extra={"url": url})
        resp = await session.get(url)

        self._check_blocked(resp)

        # Delay before first PDP to avoid burst pattern.
        await asyncio.sleep(random.uniform(1.5, 4.0))

        return extract_top_results(resp.text, top_n=6)

    async def _fetch_pdp(self, session: AsyncSession, asin: str) -> dict:
        url = f"{_AMAZON_AE_BASE}/dp/{asin}?language=en_AE"

        logger.debug("scraper.pdp.fetch", extra={"asin": asin, "url": url})
        try:
            resp = await session.get(url)
            self._check_blocked(resp)
            return extract_pdp_specs(resp.text)
        except ScraperBlockedError:
            raise
        except Exception as exc:  # noqa: BLE001
            # PDP failures are non-fatal — return empty specs rather than
            # aborting the entire fetch.
            logger.warning(
                "scraper.pdp.error",
                extra={"asin": asin, "error": str(exc)[:120]},
            )
            return {}

    @staticmethod
    def _check_blocked(resp: object) -> None:
        """Raise ScraperBlockedError if Amazon is challenging or blocking us."""
        status = getattr(resp, "status_code", None)
        url = str(getattr(resp, "url", ""))

        if status == 403:
            raise ScraperBlockedError(f"Amazon returned 403 (url={url})")
        if _CAPTCHA_PATH in url:
            raise ScraperBlockedError(f"Amazon redirected to CAPTCHA (url={url})")
