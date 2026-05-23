"""Stub fetcher Noon UAE — devuelve 3 candidatos canned por SKU.

Mismo contrato que :mod:`amazon_uae_stub` pero con menor cardinalidad
(3 candidatos) — refleja la realidad de que Noon UAE tiene catálogo más
chico que Amazon UAE para PVF industrial.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from app.services.matching.ports import CandidateRaw, Query

CHANNEL = "noon_uae"
N_CANDIDATES = 3


CANNED_BY_SKU: dict[str, list[dict[str, Any]]] = {
    "MTBR4001050": [
        {
            "external_id": "N0PEGLER50",
            "title": "Pegler Brass Ball Valve 2 inch BSP PN25",
            "brand": "Pegler",
            "price_aed": "150.00",
            "delivery_text": "3 days",
            "specs": {
                "material": "brass",
                "valve_type": "ball_valve",
                "thread": "BSP",
                "pn": "PN25",
                "norma": "EN13828",
            },
        },
        {
            "external_id": "N0NOONBR50",
            "title": "صمام كروي نحاسي 2 بوصة",
            "brand": None,
            "price_aed": "92.00",
            "delivery_text": "2 days",
            "specs": {
                "material": "brass",
                "valve_type": "ball_valve",
                "thread": "BSP",
                "pn": "PN16",
            },
        },
        {
            "external_id": "N0NPTBV50",
            "title": "Brass Ball Valve 2 Inch NPT - Plumbing",
            "brand": None,
            "price_aed": "78.00",
            "delivery_text": "1 week",
            "specs": {
                "material": "brass",
                "valve_type": "ball_valve",
                "thread": "NPT",
                "pn": "PN16",
            },
        },
    ],
}


class NoonUaeStubFetcher:
    """Stub :class:`FetcherPort` para Noon UAE."""

    @property
    def channel(self) -> str:
        return CHANNEL

    async def fetch(self, query: Query, *, sku: str | None = None) -> list[CandidateRaw]:
        candidates_raw = CANNED_BY_SKU.get(sku or "") if sku else None
        if not candidates_raw:
            candidates_raw = _synthetic(sku or query.text)
        now = datetime.now(tz=UTC)
        out: list[CandidateRaw] = []
        for c in candidates_raw[:N_CANDIDATES]:
            out.append(
                CandidateRaw(
                    source=CHANNEL,
                    external_id=str(c["external_id"]),
                    title=str(c["title"]),
                    brand=c.get("brand"),
                    price_aed=(Decimal(str(c["price_aed"])) if c.get("price_aed") else None),
                    delivery_text=c.get("delivery_text"),
                    specs=dict(c.get("specs") or {}),
                    raw_payload={
                        "stub": True,
                        "query_text": query.text,
                        "query_type": query.type,
                    },
                    fetched_at=now,
                )
            )
        return out


def _synthetic(seed: str) -> list[dict[str, Any]]:
    digest = hashlib.sha256((seed or "stub").encode()).hexdigest()
    base_price = 60 + (int(digest[4:8], 16) % 180)
    materials = ("brass", "brass", "pvc")
    threads = ("BSP", "NPT", "FLANGED")
    pns = ("PN16", "PN25", "PN10")
    brands = ("Arco", None, None)
    deliveries = ("2 days", "3 days", "2 weeks")
    out: list[dict[str, Any]] = []
    for i in range(N_CANDIDATES):
        out.append(
            {
                "external_id": f"NSTUB{digest[i * 4 : i * 4 + 8].upper()}",
                "title": f"Noon UAE candidate {i + 1} for {seed}",
                "brand": brands[i],
                "price_aed": Decimal(base_price + i * 9),
                "delivery_text": deliveries[i],
                "specs": {
                    "material": materials[i],
                    "valve_type": "ball_valve",
                    "thread": threads[i],
                    "pn": pns[i],
                },
            }
        )
    return out
