"""Adapter Noon Partner API real (Sprint 4 SCAFFOLD).

Noon UAE no expone una SP-API equivalente; el adapter usa la Partner API
documentada por Noon (token-based auth). MODO INFRAESTRUCTURAL: cableado
con httpx + tenacity retry pero fallback al stub Sprint 3 cuando no hay
credenciales o ``MT_LIVE_NETWORK != true``.
"""

from __future__ import annotations

import logging
import os
from datetime import UTC, datetime
from typing import Any

import httpx
from tenacity import (
    AsyncRetrying,
    RetryError,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from app.services.channel_mirror.adapters.noon_api_stub import NoonApiStub
from app.services.channel_mirror.ports import LiveListing, PublishResult

logger = logging.getLogger(__name__)

CHANNEL_CODE = "noon_uae"
_DEFAULT_BASE_URL = "https://partner.noon.com/api/v1"
_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_RETRY_ATTEMPTS = 3


def parse_noon_listing(payload: dict[str, Any]) -> dict[str, Any]:
    """Pure-function parser de un listing Noon → dict canonical fields."""
    item = payload.get("item") or payload
    return {
        "noon_id": item.get("noon_sku") or item.get("psku") or "",
        "title_en": item.get("title_en") or item.get("title") or "",
        "title_ar": item.get("title_ar"),
        "brand": item.get("brand"),
        "price_aed": item.get("price"),
        "stock_qty": item.get("stock") or 0,
    }


class NoonRealApiAdapter:
    channel_code: str = CHANNEL_CODE

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        stub: NoonApiStub | None = None,
    ) -> None:
        self._http_client = http_client
        self._owns_client = http_client is None
        self._stub = stub or NoonApiStub()

    def _live_enabled(self) -> bool:
        val = os.environ.get("MT_LIVE_NETWORK", "false").strip().lower()
        return val in {"1", "true", "yes", "on"}

    def _has_credentials(self) -> bool:
        return bool(os.environ.get("NOON_PARTNER_API_KEY"))

    async def _http(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_S)
        return self._http_client

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _call_api(
        self, method: str, path: str, *, json: Any = None, params: Any = None
    ) -> dict[str, Any]:
        client = await self._http()
        base_url = os.environ.get("NOON_PARTNER_BASE_URL", _DEFAULT_BASE_URL)
        api_key = os.environ["NOON_PARTNER_API_KEY"]
        url = f"{base_url}{path}"
        headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
        retryer = AsyncRetrying(
            stop=stop_after_attempt(_DEFAULT_RETRY_ATTEMPTS),
            wait=wait_exponential(multiplier=1.0, max=4.0),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )
        async for attempt in retryer:
            with attempt:
                resp = await client.request(method, url, json=json, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        raise RuntimeError("unreachable")

    async def pull_listing(
        self, sku: str, external_id: str | None = None
    ) -> LiveListing:
        if not self._live_enabled() or not self._has_credentials():
            return await self._stub.pull_listing(sku, external_id=external_id)

        try:
            payload = await self._call_api(
                "GET",
                f"/listings/{external_id or sku}",
            )
        except (RetryError, httpx.HTTPError) as exc:
            logger.exception("noon.pull_listing failed: %s", exc)
            return await self._stub.pull_listing(sku, external_id=external_id)

        parsed = parse_noon_listing(payload)
        return LiveListing(
            channel_code=self.channel_code,
            external_id=parsed["noon_id"] or (external_id or ""),
            sku=sku,
            fields=parsed,
            buybox_state="none",
            stock_qty=parsed.get("stock_qty"),
            fetched_at=datetime.now(tz=UTC),
            raw={"noon": True, "raw": payload},
        )

    async def push_diff(
        self,
        sku: str,
        external_id: str | None,
        diff_payload: dict[str, Any],
    ) -> PublishResult:
        if not self._live_enabled() or not self._has_credentials():
            return await self._stub.push_diff(sku, external_id, diff_payload)

        try:
            payload = await self._call_api(
                "PATCH",
                f"/listings/{external_id or sku}",
                json=diff_payload,
            )
        except (RetryError, httpx.HTTPError) as exc:
            logger.exception("noon.push_diff failed: %s", exc)
            return PublishResult(
                ok=False,
                submission_id=None,
                accepted_fields=[],
                rejected_fields=list(diff_payload.keys()),
                message=f"noon_error: {exc}",
                raw={"noon": True, "error": str(exc)},
            )

        return PublishResult(
            ok=True,
            submission_id=str(payload.get("submission_id", "")),
            accepted_fields=list(diff_payload.keys()),
            rejected_fields=[],
            message="submitted to Noon partner API",
            raw={"noon": True, "raw": payload},
        )


__all__ = ["NoonRealApiAdapter", "parse_noon_listing"]
