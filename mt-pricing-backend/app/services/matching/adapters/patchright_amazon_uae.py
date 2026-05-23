"""Tier 2 live scraper — Amazon UAE via patchright (Chromium anti-detect).

Replaces ``CurlCffiAmazonUaeFetcher`` as the primary live scraper when it is
blocked by Amazon, giving the pipeline a second attempt with a full headless
browser before falling back to the stub.

Architecture:
- Uses ``patchright`` (Playwright fork with C-level anti-detection patches at
  the V8/CDP layer) to evade bot-detection that defeats curl_cffi.
- 1 browser per worker process, N pages per task (singleton pattern). The
  browser is created lazily on the first :meth:`fetch` call and kept alive for
  the lifetime of the Celery worker process.
- An ``asyncio.Lock`` protects singleton initialisation to avoid race
  conditions if multiple coroutines call :meth:`fetch` before the browser is
  ready.
- Reuses the same HTML extractors as Tier 1:
    ``extract_top_results()`` (SERP) and ``extract_pdp_specs()`` (PDP).
- Raises :class:`ScraperBlockedError` on 403 / CAPTCHA so the adapter_registry
  can fall back to the stub.

Env vars (all optional):
    SCRAPER_BROWSER_CHANNEL  patchright channel: "chromium" (default), "chrome", "msedge"
    SCRAPER_PROXY_URL        HTTP/SOCKS5 proxy URL (e.g. "http://user:pass@host:port")
    SCRAPER_HEADLESS         "true" (default) or "false"
    SCRAPER_TIMEOUT          Navigation timeout in ms (default 30000)

Lifecycle (Celery worker entrypoint must call these):
    await PatchrightAmazonUaeFetcher.start()   # launch browser
    ...
    await PatchrightAmazonUaeFetcher.stop()    # close browser on shutdown
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
from datetime import datetime, timezone
from decimal import Decimal
from urllib.parse import quote_plus

from app.services.matching.extractors.pdp_extractor import extract_pdp_specs
from app.services.matching.extractors.serp_extractor import extract_top_results
from app.services.matching.ports import CandidateRaw, Query
from app.services.matching.scraper_errors import ScraperBlockedError

logger = logging.getLogger(__name__)

_AMAZON_AE_BASE = "https://www.amazon.ae"
_CAPTCHA_PATH = "/errors/validatecaptcha"

_DEFAULT_CHANNEL = "chromium"
_DEFAULT_TIMEOUT_MS = 30_000

# Realistic UA for Amazon UAE (en-AE).
_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


class PatchrightAmazonUaeFetcher:
    """Tier 2 live fetcher for Amazon UAE using patchright headless Chromium.

    Implements :class:`app.services.matching.ports.FetcherPort`.

    Browser lifecycle is fully contained within :meth:`fetch` using
    ``async with async_playwright()``. This makes the fetcher safe for
    Celery prefork workers where each task runs in a fresh asyncio.run()
    event loop.
    """

    channel = "amazon_uae"

    def __init__(self) -> None:
        self._browser_channel: str = os.environ.get("SCRAPER_BROWSER_CHANNEL", _DEFAULT_CHANNEL)
        self._proxy_url: str | None = os.environ.get("SCRAPER_PROXY_URL") or None
        self._headless: bool = os.environ.get("SCRAPER_HEADLESS", "true").strip().lower() != "false"
        self._timeout_ms: int = int(os.environ.get("SCRAPER_TIMEOUT", _DEFAULT_TIMEOUT_MS))

    # ------------------------------------------------------------------
    # FetcherPort interface
    # ------------------------------------------------------------------

    async def fetch(self, query: Query, *, sku: str | None = None) -> list[CandidateRaw]:
        """Fetch live candidates from Amazon UAE using a headless Chromium browser.

        Steps:
            1. Launch a fresh browser for this fetch (owned via async with).
            2. GET SERP for ``query.text`` and extract top ASINs.
            3. GET each PDP in a new page to collect structured specs.
            4. Close the browser; map results to :class:`CandidateRaw`.

        Browser lifecycle is contained within this method — no module-level
        singleton. This is required for Celery prefork workers where each
        task runs inside a fresh asyncio.run() event loop.

        Raises:
            ScraperBlockedError: if Amazon returns 403 or redirects to CAPTCHA
                at the SERP level (PDP blocks are silently swallowed as empty specs).
        """
        from patchright.async_api import async_playwright  # type: ignore[import]  # noqa: PLC0415

        now = datetime.now(tz=timezone.utc)

        async with async_playwright() as pw:
            launcher = getattr(pw, self._browser_channel, pw.chromium)
            launch_kwargs: dict = {
                "headless": self._headless,
                "args": [
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu",
                    "--no-zygote",
                    "--single-process",
                    "--disable-setuid-sandbox",
                    "--disable-software-rasterizer",
                ],
            }
            if self._proxy_url:
                launch_kwargs["proxy"] = {"server": self._proxy_url}

            logger.info(
                "patchright.browser.starting",
                extra={"channel": self._browser_channel, "headless": self._headless},
            )
            browser = await launcher.launch(**launch_kwargs)
            logger.info("patchright.browser.ready")

            context_kwargs: dict = {
                "viewport": {"width": 1280, "height": 800},
                "locale": "en-AE",
                "user_agent": _USER_AGENT,
                "extra_http_headers": {
                    "Accept-Language": "en-AE,en;q=0.9,ar;q=0.8",
                    "Accept": (
                        "text/html,application/xhtml+xml,application/xml;q=0.9,"
                        "image/avif,image/webp,image/apng,*/*;q=0.8"
                    ),
                },
            }
            context = await browser.new_context(**context_kwargs)

            serp_results = await self._fetch_serp_with(context, query)

            candidates: list[CandidateRaw] = []
            for item in serp_results:
                asin = item.get("asin")
                if not asin:
                    continue

                # Polite delay between PDP requests to mimic human navigation.
                await asyncio.sleep(random.uniform(1.5, 4.0))

                pdp_specs = await self._fetch_pdp_with(context, asin)

                price_raw = item.get("price_aed")
                price_aed: Decimal | None = price_raw if isinstance(price_raw, Decimal) else None

                # delivery_text may be extracted from the rendered PDP (section 4d).
                delivery_text_pdp = str(pdp_specs.get("delivery_text") or "") or None

                candidates.append(
                    CandidateRaw(
                        source=self.channel,
                        external_id=asin,
                        title=str(item.get("title") or pdp_specs.get("title_pdp") or ""),
                        brand=str(pdp_specs.get("brand_name") or "") or None,
                        price_aed=price_aed,
                        delivery_text=delivery_text_pdp,
                        specs={
                            k: v
                            for k, v in pdp_specs.items()
                            if k not in {"title_pdp", "canonical_url", "raw_pairs"}
                        },
                        raw_payload={
                            "asin": asin,
                            "image_url": item.get("image_url", ""),
                            "url": item.get("url", ""),
                            "query_text": query.text,
                            "query_type": query.type,
                            "tier": "patchright",
                        },
                        fetched_at=now,
                    )
                )

        return candidates

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    async def _fetch_serp_with(self, context: object, query: Query) -> list[dict]:
        """Navigate to SERP using ``context``; return extracted results."""
        url = f"{_AMAZON_AE_BASE}/s?k={quote_plus(query.text)}"
        if query.dept:
            url += f"&i={query.dept}"
        if query.category_node:
            url += f"&rh=n:{query.category_node}"
        url += "&language=en_AE"
        logger.debug("patchright.serp.fetch", extra={"url": url})

        html, final_url = await self._page_get_with(context, url)
        self._check_blocked(200, final_url)

        # Polite delay before first PDP.
        await asyncio.sleep(random.uniform(1.5, 4.0))

        return extract_top_results(html, top_n=6)

    async def _fetch_pdp_with(self, context: object, asin: str) -> dict:
        """Navigate to PDP using ``context``; return specs or empty dict."""
        url = f"{_AMAZON_AE_BASE}/dp/{asin}?language=en_AE"
        logger.debug("patchright.pdp.fetch", extra={"asin": asin, "url": url})

        try:
            html, final_url = await self._page_get_with(context, url)
            self._check_blocked(200, final_url)
            return extract_pdp_specs(html)
        except ScraperBlockedError:
            raise
        except Exception as exc:  # noqa: BLE001
            # PDP failures are non-fatal — return empty specs rather than
            # aborting the entire fetch.
            logger.warning(
                "patchright.pdp.error",
                extra={"asin": asin, "error": str(exc)[:120]},
            )
            return {}

    async def _page_get_with(self, context: object, url: str) -> tuple[str, str]:
        """Open a fresh page in ``context``, navigate to ``url``, return (html, final_url)."""
        page = await context.new_page()  # type: ignore[union-attr]
        try:
            response = await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self._timeout_ms,
            )
            status = response.status if response is not None else 0
            final_url = page.url

            if status == 403:
                raise ScraperBlockedError(f"patchright: Amazon returned 403 (url={final_url})")

            html: str = await page.content()
        finally:
            await page.close()

        return html, final_url

    @staticmethod
    def _check_blocked(status: int, url: str) -> None:
        """Raise ScraperBlockedError if Amazon is challenging or blocking us."""
        if status == 403:
            raise ScraperBlockedError(f"patchright: Amazon returned 403 (url={url})")
        if _CAPTCHA_PATH in url:
            raise ScraperBlockedError(f"patchright: Amazon redirected to CAPTCHA (url={url})")


__all__ = ["PatchrightAmazonUaeFetcher"]
