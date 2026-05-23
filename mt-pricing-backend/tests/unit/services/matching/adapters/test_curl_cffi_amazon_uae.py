"""Unit tests for CurlCffiAmazonUaeFetcher (app/services/matching/adapters/curl_cffi_amazon_uae.py).

No real HTTP or curl_cffi session is used — all network I/O is mocked.
"""

from __future__ import annotations

import os
from decimal import Decimal
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.matching.adapters.curl_cffi_amazon_uae import (
    _AMAZON_AE_BASE,
    _CAPTCHA_PATH,
    CurlCffiAmazonUaeFetcher,
    ScraperBlockedError,
)
from app.services.matching.ports import CandidateRaw, Query

pytestmark = pytest.mark.unit

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_query(**kwargs) -> Query:
    defaults = dict(text="brass ball valve 2 inch", source="test", lang="en")
    defaults.update(kwargs)
    return Query(**defaults)


def _make_response(
    *, status_code: int = 200, url: str = "https://www.amazon.ae/s?k=valve", text: str = ""
) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.url = url
    resp.text = text
    return resp


def _make_fetcher(**env_overrides) -> CurlCffiAmazonUaeFetcher:
    """Instantiate the fetcher with optional env-var overrides."""
    with patch.dict(os.environ, env_overrides, clear=False):
        return CurlCffiAmazonUaeFetcher()


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------


def test_default_impersonate_pool_has_three_entries() -> None:
    fetcher = _make_fetcher()
    assert len(fetcher._impersonate_pool) == 3
    assert "chrome124" in fetcher._impersonate_pool


def test_custom_impersonate_pool_env_var() -> None:
    fetcher = _make_fetcher(SCRAPER_IMPERSONATE_POOL="chrome120,firefox110")
    assert fetcher._impersonate_pool == ["chrome120", "firefox110"]


def test_single_impersonate_env_var_fallback() -> None:
    with patch.dict(
        os.environ, {"SCRAPER_IMPERSONATE_POOL": "", "SCRAPER_IMPERSONATE": "chrome99"}, clear=False
    ):
        fetcher = CurlCffiAmazonUaeFetcher()
    assert fetcher._impersonate_pool == ["chrome99"]


def test_default_timeout() -> None:
    fetcher = _make_fetcher()
    assert fetcher._timeout == 30


def test_custom_timeout_env_var() -> None:
    fetcher = _make_fetcher(SCRAPER_TIMEOUT="45")
    assert fetcher._timeout == 45


def test_proxy_is_none_when_env_not_set() -> None:
    with patch.dict(os.environ, {}, clear=False):
        # Ensure the key is absent
        env = {k: v for k, v in os.environ.items() if k != "SCRAPER_PROXY_URL"}
        with patch.dict(os.environ, env, clear=True):
            fetcher = CurlCffiAmazonUaeFetcher()
    assert fetcher._proxy is None


def test_proxy_set_from_env_var() -> None:
    fetcher = _make_fetcher(SCRAPER_PROXY_URL="http://user:pass@proxy:8080")
    assert fetcher._proxy == "http://user:pass@proxy:8080"


def test_channel_attribute() -> None:
    fetcher = _make_fetcher()
    assert fetcher.channel == "amazon_uae"


# ---------------------------------------------------------------------------
# _check_blocked
# ---------------------------------------------------------------------------


def test_check_blocked_passes_on_200() -> None:
    resp = _make_response(status_code=200)
    CurlCffiAmazonUaeFetcher._check_blocked(resp)  # should not raise


def test_check_blocked_raises_on_403() -> None:
    resp = _make_response(status_code=403, url="https://www.amazon.ae/dp/B001")
    with pytest.raises(ScraperBlockedError) as exc_info:
        CurlCffiAmazonUaeFetcher._check_blocked(resp)
    assert "403" in str(exc_info.value)


def test_check_blocked_raises_on_captcha_redirect() -> None:
    captcha_url = f"https://www.amazon.ae{_CAPTCHA_PATH}?..."
    resp = _make_response(status_code=200, url=captcha_url)
    with pytest.raises(ScraperBlockedError) as exc_info:
        CurlCffiAmazonUaeFetcher._check_blocked(resp)
    assert "CAPTCHA" in str(exc_info.value)


def test_check_blocked_raises_on_403_captcha_combo() -> None:
    captcha_url = f"https://www.amazon.ae{_CAPTCHA_PATH}"
    resp = _make_response(status_code=403, url=captcha_url)
    with pytest.raises(ScraperBlockedError):
        CurlCffiAmazonUaeFetcher._check_blocked(resp)


def test_check_blocked_passes_on_non_captcha_redirect() -> None:
    resp = _make_response(status_code=200, url="https://www.amazon.ae/dp/B001?language=en_AE")
    CurlCffiAmazonUaeFetcher._check_blocked(resp)  # should not raise


# ---------------------------------------------------------------------------
# _make_session
# ---------------------------------------------------------------------------


def test_make_session_returns_async_session_instance() -> None:
    fetcher = _make_fetcher()
    mock_session_cls = MagicMock()
    with patch(
        "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession", mock_session_cls
    ):
        fetcher._make_session()
    mock_session_cls.assert_called_once()
    call_kwargs = mock_session_cls.call_args[1]
    assert "impersonate" in call_kwargs
    assert call_kwargs["impersonate"] in fetcher._impersonate_pool


def test_make_session_passes_proxy_when_set() -> None:
    fetcher = _make_fetcher(SCRAPER_PROXY_URL="http://proxy:8080")
    mock_session_cls = MagicMock()
    with patch(
        "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession", mock_session_cls
    ):
        fetcher._make_session()
    call_kwargs = mock_session_cls.call_args[1]
    assert "proxies" in call_kwargs
    assert call_kwargs["proxies"]["https"] == "http://proxy:8080"


def test_make_session_no_proxy_key_when_proxy_not_set() -> None:
    with patch.dict(
        os.environ, {k: v for k, v in os.environ.items() if k != "SCRAPER_PROXY_URL"}, clear=True
    ):
        fetcher = CurlCffiAmazonUaeFetcher()
    mock_session_cls = MagicMock()
    with patch(
        "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession", mock_session_cls
    ):
        fetcher._make_session()
    call_kwargs = mock_session_cls.call_args[1]
    assert "proxies" not in call_kwargs


# ---------------------------------------------------------------------------
# fetch() — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_returns_candidate_list_on_success() -> None:
    fetcher = _make_fetcher()

    serp_items = [
        {
            "asin": "B001VALVE",
            "title": "Brass Ball Valve 2in",
            "price_aed": Decimal("145.00"),
            "image_url": "https://img.example.com/x.jpg",
            "url": "https://www.amazon.ae/dp/B001VALVE",
        },
    ]
    pdp_specs = {
        "brand_name": "Pegler",
        "material": "brass",
        "size": "2 inch",
        "title_pdp": "Brass Ball Valve 2in",
    }

    serp_resp = _make_response(text="<html>serp</html>")
    pdp_resp = _make_response(text="<html>pdp</html>")

    mock_session = AsyncMock()
    mock_session.get.side_effect = [serp_resp, pdp_resp]
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=serp_items,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_pdp_specs",
            return_value=pdp_specs,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        query = _make_query(text="brass ball valve")
        results = await fetcher.fetch(query)

    assert len(results) == 1
    candidate = results[0]
    assert isinstance(candidate, CandidateRaw)
    assert candidate.external_id == "B001VALVE"
    assert candidate.source == "amazon_uae"
    assert candidate.price_aed == Decimal("145.00")
    assert candidate.brand == "Pegler"
    assert candidate.specs.get("material") == "brass"


@pytest.mark.asyncio
async def test_fetch_skips_serp_item_without_asin() -> None:
    fetcher = _make_fetcher()

    serp_items = [
        {"asin": "", "title": "No ASIN item"},
        {
            "asin": "B002VALID",
            "title": "Valid item",
            "price_aed": Decimal("50.00"),
            "image_url": "",
            "url": "",
        },
    ]
    pdp_specs: dict = {}

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    serp_resp = _make_response()
    pdp_resp = _make_response()
    mock_session.get.side_effect = [serp_resp, pdp_resp]

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=serp_items,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_pdp_specs",
            return_value=pdp_specs,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        results = await fetcher.fetch(_make_query())

    assert len(results) == 1
    assert results[0].external_id == "B002VALID"


@pytest.mark.asyncio
async def test_fetch_raises_scraper_blocked_on_403_serp() -> None:
    fetcher = _make_fetcher()

    serp_resp = _make_response(status_code=403)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = serp_resp

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ScraperBlockedError):
            await fetcher.fetch(_make_query())


@pytest.mark.asyncio
async def test_fetch_raises_scraper_blocked_on_captcha_serp() -> None:
    fetcher = _make_fetcher()

    captcha_url = f"{_AMAZON_AE_BASE}{_CAPTCHA_PATH}?fld=val"
    serp_resp = _make_response(status_code=200, url=captcha_url)

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = serp_resp

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ScraperBlockedError):
            await fetcher.fetch(_make_query())


@pytest.mark.asyncio
async def test_fetch_pdp_error_returns_empty_specs_not_raises() -> None:
    """PDP failure is non-fatal: candidate is still returned with empty specs."""
    fetcher = _make_fetcher()

    serp_items = [
        {
            "asin": "B003VALVE",
            "title": "Valve",
            "price_aed": Decimal("99.00"),
            "image_url": "",
            "url": "",
        },
    ]

    serp_resp = _make_response()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    # PDP request raises a generic exception
    mock_session.get.side_effect = [serp_resp, Exception("connection reset")]

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=serp_items,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        results = await fetcher.fetch(_make_query())

    assert len(results) == 1
    assert results[0].specs == {}


@pytest.mark.asyncio
async def test_fetch_pdp_blocked_propagates_scraper_blocked_error() -> None:
    """ScraperBlockedError from PDP is re-raised (not swallowed)."""
    fetcher = _make_fetcher()

    serp_items = [
        {"asin": "B004VALVE", "title": "Valve", "price_aed": None, "image_url": "", "url": ""},
    ]

    serp_resp = _make_response()
    pdp_resp = _make_response(status_code=403, url="https://www.amazon.ae/dp/B004VALVE")

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = [serp_resp, pdp_resp]

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=serp_items,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        with pytest.raises(ScraperBlockedError):
            await fetcher.fetch(_make_query())


# ---------------------------------------------------------------------------
# SERP URL construction
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_serp_url_contains_encoded_query() -> None:
    fetcher = _make_fetcher()
    captured_urls: list[str] = []

    serp_resp = _make_response()

    async def fake_get(url: str, **kw: Any) -> MagicMock:
        captured_urls.append(url)
        return serp_resp

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = fake_get

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=[],
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await fetcher.fetch(_make_query(text="brass ball valve"))

    assert len(captured_urls) == 1
    serp_url = captured_urls[0]
    assert serp_url.startswith(_AMAZON_AE_BASE)
    assert "brass+ball+valve" in serp_url or "brass%20ball%20valve" in serp_url
    assert "language=en_AE" in serp_url


@pytest.mark.asyncio
async def test_fetch_serp_url_includes_dept_when_set() -> None:
    fetcher = _make_fetcher()
    captured_urls: list[str] = []

    serp_resp = _make_response()

    async def fake_get(url: str, **kw: Any) -> MagicMock:
        captured_urls.append(url)
        return serp_resp

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = fake_get

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=[],
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await fetcher.fetch(_make_query(dept="industrial"))

    assert "i=industrial" in captured_urls[0]


@pytest.mark.asyncio
async def test_fetch_pdp_url_uses_asin_and_language() -> None:
    fetcher = _make_fetcher()
    captured_urls: list[str] = []

    serp_resp = _make_response()
    pdp_resp = _make_response()

    async def fake_get(url: str, **kw: Any) -> MagicMock:
        captured_urls.append(url)
        return serp_resp if len(captured_urls) == 1 else pdp_resp

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = fake_get

    serp_items = [
        {"asin": "BASIN123", "title": "Valve", "price_aed": None, "image_url": "", "url": ""}
    ]

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=serp_items,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_pdp_specs", return_value={}
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await fetcher.fetch(_make_query())

    assert len(captured_urls) == 2
    pdp_url = captured_urls[1]
    assert "/dp/BASIN123" in pdp_url
    assert "language=en_AE" in pdp_url


# ---------------------------------------------------------------------------
# Price fallback from PDP
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_uses_pdp_price_when_serp_price_is_none() -> None:
    fetcher = _make_fetcher()

    serp_items = [
        {"asin": "B005VALVE", "title": "Valve", "price_aed": None, "image_url": "", "url": ""},
    ]
    pdp_specs = {"price_aed": "200.50", "brand_name": "Aalberts"}

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.side_effect = [_make_response(), _make_response()]

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=serp_items,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_pdp_specs",
            return_value=pdp_specs,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        results = await fetcher.fetch(_make_query())

    assert results[0].price_aed == Decimal("200.50")


@pytest.mark.asyncio
async def test_fetch_returns_empty_list_when_no_serp_results() -> None:
    fetcher = _make_fetcher()

    mock_session = AsyncMock()
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)
    mock_session.get.return_value = _make_response()

    with (
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.AsyncSession",
            return_value=mock_session,
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.extract_top_results",
            return_value=[],
        ),
        patch(
            "app.services.matching.adapters.curl_cffi_amazon_uae.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        results = await fetcher.fetch(_make_query())

    assert results == []
