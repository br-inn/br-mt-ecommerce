"""Stub fetcher Shopify UAE — devuelve 3 candidatos sintéticos por SKU.

No hay adapter real todavía (Fase 1.5+). Misma interfaz que los stubs
de Amazon/Noon para que el runner pueda tratar los tres canales de forma
uniforme en el POC.

Canal registrado: ``shopify_uae``
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.services.matching.ports import CandidateRaw, Query

CHANNEL = "shopify_uae"
N_CANDIDATES = 3


class ShopifyUaeStubFetcher:
    """Stub :class:`FetcherPort` para Shopify UAE."""

    @property
    def channel(self) -> str:
        return CHANNEL

    async def fetch(self, query: Query, *, sku: str | None = None) -> list[CandidateRaw]:
        candidates_raw = _synthetic(sku or query.text)
        now = datetime.now(tz=timezone.utc)
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
                        "channel": CHANNEL,
                        "query_text": query.text,
                    },
                    fetched_at=now,
                )
            )
        return out


def _synthetic(seed: str) -> list[dict[str, Any]]:
    digest = hashlib.sha256((seed or "shopify_stub").encode()).hexdigest()
    base_price = 70 + (int(digest[8:12], 16) % 150)
    materials = ("brass", "ss316", "pvc")
    threads = ("BSP", "BSP", "NPT")
    pns = ("PN25", "PN16", "PN10")
    brands = ("Pegler", "Apollo", None)
    deliveries = ("3 days", "2 days", "1 week")
    out: list[dict[str, Any]] = []
    for i in range(N_CANDIDATES):
        out.append(
            {
                "external_id": f"SSTUB{digest[i * 5 : i * 5 + 10].upper()}",
                "title": f"Shopify UAE candidate {i + 1} for {seed}",
                "brand": brands[i],
                "price_aed": Decimal(base_price + i * 11),
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


__all__ = ["ShopifyUaeStubFetcher", "CHANNEL"]
