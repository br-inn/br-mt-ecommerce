"""Adapter Amazon SP-API real (Sprint 4 SCAFFOLD, US-1A-09-05).

MODO INFRAESTRUCTURAL: cableado contra ``getCatalogItem`` /
``getInventorySummaries`` / ``getPricing`` con httpx + LWA token refresh +
tenacity retry + cache hook (TTL del cliente del adapter), pero sin
ejercitar la red real hasta que ``MT_LIVE_NETWORK=true`` y las
credenciales (``SP_API_REFRESH_TOKEN``, ``SP_API_LWA_CLIENT_ID``,
``SP_API_LWA_CLIENT_SECRET``, ``AWS_ROLE_ARN_SP_API``) estén configuradas.

Fallback transparente al stub Sprint 3
(:class:`AmazonSPApiStub`) cuando faltan creds o el flag está apagado.

NOTA: la implementación NO firma AWS Sigv4 ni gestiona LWA OAuth en este
scaffold — sólo deja el wire (método ``_refresh_lwa_token`` con TODO,
método ``_call_sp_api`` con httpx + retry). El agente que active la red
real implementará Sigv4 (libs candidatas: ``boto3`` + ``requests-aws4auth``,
o ``python-amazon-sp-api``).
"""

from __future__ import annotations

import logging
import os
import time
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

from app.services.channel_mirror.adapters.amazon_sp_api_stub import AmazonSPApiStub
from app.services.channel_mirror.ports import LiveListing, PublishResult

logger = logging.getLogger(__name__)

CHANNEL_CODE = "amazon_uae"
MARKETPLACE_ID = "A2VIGQ35RCS4UG"  # Amazon.ae
_DEFAULT_BASE_URL = "https://sellingpartnerapi-eu.amazon.com"
_DEFAULT_LWA_URL = "https://api.amazon.com/auth/o2/token"
_DEFAULT_TIMEOUT_S = 30.0
_DEFAULT_RETRY_ATTEMPTS = 3
_LWA_TOKEN_TTL_S = 3500  # margen de seguridad sobre el 3600 default


def parse_catalog_item(payload: dict[str, Any]) -> dict[str, Any]:
    """Parser pure-function — extrae los fields canonical de la respuesta SP-API.

    Útil para tests (no necesita HTTP). Espera la shape de
    ``getCatalogItem``::

        {"asin": ..., "attributes": {"item_name": [...], ...}, ...}
    """
    asin = payload.get("asin", "")
    attributes = payload.get("attributes") or {}
    summaries = payload.get("summaries") or []

    def _attr(key: str) -> str | None:
        v = attributes.get(key)
        if isinstance(v, list) and v:
            inner = v[0]
            if isinstance(inner, dict):
                return inner.get("value")
            return str(inner)
        if isinstance(v, dict):
            return v.get("value")
        if v is not None:
            return str(v)
        return None

    title = _attr("item_name") or ""
    if not title and summaries:
        s0 = summaries[0]
        if isinstance(s0, dict):
            title = s0.get("itemName") or ""

    return {
        "asin": asin,
        "title_en": title,
        "brand": _attr("brand"),
        "material": _attr("material"),
        "HS_code": _attr("hs_code"),
    }


class AmazonSPApiAdapter:
    """Adapter SP-API real (modo scaffold).

    Para tests: inyectar ``http_client`` y ``stub`` (fallback). Para prod:
    poblar env vars y dejar que el adapter abra su propio cliente.
    """

    channel_code: str = CHANNEL_CODE

    def __init__(
        self,
        *,
        http_client: httpx.AsyncClient | None = None,
        stub: AmazonSPApiStub | None = None,
    ) -> None:
        self._http_client = http_client
        self._owns_client = http_client is None
        self._stub = stub or AmazonSPApiStub()
        self._lwa_token: str | None = None
        self._lwa_token_expires_at: float = 0.0

    def _live_enabled(self) -> bool:
        val = os.environ.get("MT_LIVE_NETWORK", "false").strip().lower()
        return val in {"1", "true", "yes", "on"}

    def _has_credentials(self) -> bool:
        return bool(
            os.environ.get("SP_API_REFRESH_TOKEN")
            and os.environ.get("SP_API_LWA_CLIENT_ID")
            and os.environ.get("SP_API_LWA_CLIENT_SECRET")
        )

    async def _http(self) -> httpx.AsyncClient:
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(timeout=_DEFAULT_TIMEOUT_S)
        return self._http_client

    async def aclose(self) -> None:
        if self._owns_client and self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None

    async def _refresh_lwa_token(self) -> str:
        """Pide un access token LWA con el refresh token.

        SCAFFOLD: hace el POST real pero sin firmar AWS. Cuando se
        active red real, validar manejo de scopes + reintentos.
        """
        client = await self._http()
        lwa_url = os.environ.get("SP_API_LWA_URL", _DEFAULT_LWA_URL)
        body = {
            "grant_type": "refresh_token",
            "refresh_token": os.environ["SP_API_REFRESH_TOKEN"],
            "client_id": os.environ["SP_API_LWA_CLIENT_ID"],
            "client_secret": os.environ["SP_API_LWA_CLIENT_SECRET"],
        }
        resp = await client.post(lwa_url, data=body)
        resp.raise_for_status()
        data = resp.json()
        token: str = data["access_token"]
        self._lwa_token = token
        self._lwa_token_expires_at = time.monotonic() + _LWA_TOKEN_TTL_S
        return token

    async def _ensure_token(self) -> str:
        if self._lwa_token and time.monotonic() < self._lwa_token_expires_at:
            return self._lwa_token
        return await self._refresh_lwa_token()

    async def _call_sp_api(
        self, method: str, path: str, *, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        client = await self._http()
        token = await self._ensure_token()
        base_url = os.environ.get("SP_API_BASE_URL", _DEFAULT_BASE_URL)
        url = f"{base_url}{path}"
        headers = {"x-amz-access-token": token}
        retryer = AsyncRetrying(
            stop=stop_after_attempt(_DEFAULT_RETRY_ATTEMPTS),
            wait=wait_exponential(multiplier=1.0, max=4.0),
            retry=retry_if_exception_type(httpx.HTTPError),
            reraise=True,
        )
        async for attempt in retryer:
            with attempt:
                resp = await client.request(method, url, params=params, headers=headers)
                resp.raise_for_status()
                return resp.json()
        raise RuntimeError("unreachable")

    async def pull_listing(self, sku: str, external_id: str | None = None) -> LiveListing:
        if not self._live_enabled() or not self._has_credentials():
            return await self._stub.pull_listing(sku, external_id=external_id)

        asin = external_id
        if not asin:
            return await self._stub.pull_listing(sku, external_id=external_id)

        try:
            payload = await self._call_sp_api(
                "GET",
                f"/catalog/2022-04-01/items/{asin}",
                params={"marketplaceIds": MARKETPLACE_ID, "includedData": "attributes,summaries"},
            )
        except (RetryError, httpx.HTTPError) as exc:
            logger.exception("sp_api.pull_listing failed: %s", exc)
            return await self._stub.pull_listing(sku, external_id=external_id)

        parsed = parse_catalog_item(payload)
        return LiveListing(
            channel_code=self.channel_code,
            external_id=parsed["asin"] or asin,
            sku=sku,
            fields=parsed,
            buybox_state="none",  # se rellena con getPricing en una llamada paralela
            fetched_at=datetime.now(tz=UTC),
            raw={"sp_api": True, "raw": payload},
        )

    async def push_diff(
        self,
        sku: str,
        external_id: str | None,
        diff_payload: dict[str, Any],
    ) -> PublishResult:
        if not self._live_enabled() or not self._has_credentials():
            return await self._stub.push_diff(sku, external_id, diff_payload)

        if not external_id:
            return PublishResult(
                ok=False,
                submission_id=None,
                accepted_fields=[],
                rejected_fields=list(diff_payload.keys()),
                message="external_id (ASIN) requerido para submitListings",
                raw={"sp_api": True, "reason": "missing_asin"},
            )

        seller_id = os.environ.get("SP_API_SELLER_ID", "")
        try:
            payload = await self._call_sp_api(
                "PATCH",
                f"/listings/2021-08-01/items/{seller_id}/{external_id}",
                params={"marketplaceIds": MARKETPLACE_ID},
            )
        except (RetryError, httpx.HTTPError) as exc:
            logger.exception("sp_api.push_diff failed: %s", exc)
            return PublishResult(
                ok=False,
                submission_id=None,
                accepted_fields=[],
                rejected_fields=list(diff_payload.keys()),
                message=f"sp_api_error: {exc}",
                raw={"sp_api": True, "error": str(exc)},
            )

        return PublishResult(
            ok=True,
            submission_id=str(payload.get("submissionId", "")),
            accepted_fields=list(diff_payload.keys()),
            rejected_fields=[],
            message="submitted to SP-API",
            raw={"sp_api": True, "raw": payload},
        )


__all__ = ["AmazonSPApiAdapter", "parse_catalog_item"]
