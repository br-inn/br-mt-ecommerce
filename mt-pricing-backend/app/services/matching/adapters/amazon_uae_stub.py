"""Stub fetcher Amazon UAE — devuelve 5 candidatos canned por SKU.

No hace ninguna llamada de red. Cubre la interfaz :class:`FetcherPort` y
permite que :class:`MatchService` se ejercite end-to-end sin Bright Data.
Cuando llegue el adapter real (Bright Data Web Scraper) se reemplaza este
módulo manteniendo el mismo contrato.

Generación de los stubs:
- Si el SKU está en el mapeo ``CANNED_BY_SKU`` se devuelve el dataset
  curado (refleja casos reales del demo v5.1: Pegler, Arco, etc.).
- Si no está, se sintetizan 5 candidatos derivando ASIN ficticio del SKU —
  determinístico (mismo SKU → mismos candidatos siempre, útil para tests).
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from app.services.matching.ports import CandidateRaw, Query

CHANNEL = "amazon_uae"
N_CANDIDATES = 5


# Curated canned data for demo SKUs — fácil expandir.
CANNED_BY_SKU: dict[str, list[dict[str, Any]]] = {
    "MTBR4001050": [
        {
            "external_id": "B07PEGLER50",
            "title": "Pegler 2-Inch Brass Ball Valve, BSP Threaded, PN25",
            "brand": "Pegler",
            "price_aed": "145.50",
            "delivery_text": "2 days",
            "specs": {
                "material": "brass",
                "valve_type": "ball_valve",
                "thread": "BSP",
                "pn": "PN25",
                "norma": "EN13828",
            },
        },
        {
            "external_id": "B07ARCOBV50",
            "title": "Arco brass ball valve DN50 PN25 BSP female",
            "brand": "Arco",
            "price_aed": "132.00",
            "delivery_text": "next day",
            "specs": {
                "material": "brass",
                "valve_type": "ball_valve",
                "thread": "BSP",
                "pn": "PN25",
                "norma": "EN13828",
            },
        },
        {
            "external_id": "B07GENBV50",
            "title": "Generic 2 Inch Brass Ball Valve",
            "brand": None,
            "price_aed": "85.00",
            "delivery_text": "3 days",
            "specs": {
                "material": "brass",
                "valve_type": "ball_valve",
                "thread": "BSP",
                "pn": "PN16",
            },
        },
        {
            "external_id": "B07SS316V50",
            "title": "Stainless Steel SS316 Ball Valve 2 inch BSP",
            "brand": "Apollo",
            "price_aed": "320.00",
            "delivery_text": "1 week",
            "specs": {
                "material": "ss316",
                "valve_type": "ball_valve",
                "thread": "BSP",
                "pn": "PN40",
            },
        },
        {
            "external_id": "B07GIACGV50",
            "title": "Giacomini Brass Gate Valve DN50 PN16",
            "brand": "Giacomini",
            "price_aed": "98.50",
            "delivery_text": "4-7 days",
            "specs": {
                "material": "brass",
                "valve_type": "gate_valve",
                "thread": "BSP",
                "pn": "PN16",
            },
        },
    ],
}


class AmazonUaeStubFetcher:
    """Implementación stub del :class:`FetcherPort` para Amazon UAE."""

    @property
    def channel(self) -> str:
        return CHANNEL

    async def fetch(
        self, query: Query, *, sku: str | None = None
    ) -> list[CandidateRaw]:
        """Devuelve 5 candidatos canned para el SKU.

        El argumento ``query`` se ignora intencionalmente (stub) — el contrato
        de un fetcher real lo usaría para llamar a la API de Bright Data.
        """
        candidates_raw = CANNED_BY_SKU.get(sku or "") if sku else None
        if not candidates_raw:
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
                    price_aed=(
                        Decimal(str(c["price_aed"])) if c.get("price_aed") else None
                    ),
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
    """Genera 5 candidatos determinísticos a partir de un seed (sku/query)."""
    digest = hashlib.sha256((seed or "stub").encode()).hexdigest()
    base_price = 50 + (int(digest[:4], 16) % 200)
    materials = ("brass", "brass", "ss316", "brass", "cast_iron")
    threads = ("BSP", "BSP", "NPT", "BSP", "FLANGED")
    pns = ("PN16", "PN25", "PN40", "PN16", "PN10")
    brands = ("Pegler", None, "Apollo", "Arco", None)
    deliveries = ("next day", "2 days", "1 week", "3 days", "2 weeks")
    out: list[dict[str, Any]] = []
    for i in range(N_CANDIDATES):
        out.append(
            {
                "external_id": f"BSTUB{digest[i * 4 : i * 4 + 8].upper()}",
                "title": f"Amazon UAE candidate {i + 1} for {seed}",
                "brand": brands[i],
                "price_aed": Decimal(base_price + i * 7),
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
