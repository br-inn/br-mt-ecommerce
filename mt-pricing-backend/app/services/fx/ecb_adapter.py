"""Adapter ECB → EUR/USD reference rate; deriva EUR/AED vía peg USD/AED."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from decimal import Decimal

import httpx
from defusedxml.ElementTree import fromstring as safe_fromstring  # XXE/billion-laughs safe
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import get_settings

logger = logging.getLogger(__name__)
_NS = {"ref": "http://www.ecb.int/vocabulary/2002-08-01/eurofxref"}
_TIMEOUT_S = 30.0
_RETRY_ATTEMPTS = 3


@dataclass(frozen=True)
class EcbQuote:
    eur_usd: Decimal
    eur_aed: Decimal
    ecb_date: str
    source_ref: str


class EcbFxAdapter:
    """Descarga el XML diario de ECB y calcula EUR→AED."""

    def __init__(self, url: str | None = None, peg: Decimal | None = None) -> None:
        s = get_settings()
        self._url = url or s.ECB_FX_URL
        self._peg = peg or s.FX_USD_AED_PEG

    @retry(
        stop=stop_after_attempt(_RETRY_ATTEMPTS),
        wait=wait_exponential(multiplier=1, max=10),
        reraise=True,
    )
    async def _get(self) -> bytes:
        async with httpx.AsyncClient(timeout=_TIMEOUT_S) as client:
            resp = await client.get(self._url)
            resp.raise_for_status()
            return resp.content

    async def fetch_eur_aed(self) -> EcbQuote:
        raw = await self._get()
        root = safe_fromstring(raw)  # defusedxml — no XXE/entity expansion
        day_cube = root.find(".//ref:Cube[@time]", _NS)
        if day_cube is None:
            raise ValueError("ECB XML: no daily Cube[@time] found")
        ecb_date = day_cube.attrib["time"]
        usd: Decimal | None = None
        for c in day_cube.findall("ref:Cube", _NS):
            if c.attrib.get("currency") == "USD":
                usd = Decimal(c.attrib["rate"])
                break
        if usd is None:
            raise ValueError("ECB XML: USD rate not present")
        eur_aed = usd * self._peg
        return EcbQuote(
            eur_usd=usd,
            eur_aed=eur_aed,
            ecb_date=ecb_date,
            source_ref=f"ecb:{ecb_date}:eurusd={usd}:peg={self._peg}",
        )
