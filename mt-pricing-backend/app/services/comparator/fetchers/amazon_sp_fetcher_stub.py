"""AmazonSPFetcherStub — adapter stub determinístico para tests y dev local.

Implementa FetcherPort. No tiene dependencias externas. El precio sintético
es determinístico por ASIN (seed derivado de hash) para que los tests
sean reproducibles.
"""

from __future__ import annotations

import hashlib
import random
from datetime import UTC, datetime
from typing import Any

from app.services.comparator.fetchers import CompetitorPrice, FetcherPort

_MARKETPLACE_ID = "A2VIGQ35RCS4UG"  # Amazon.ae UAE


class AmazonSPFetcherStub:
    """Stub sin dependencias externas. Retorna precios sintéticos determinísticos."""

    async def fetch_competitor_price(self, asin: str) -> CompetitorPrice:
        # Seed por ASIN para determinismo en tests
        seed = int(hashlib.md5(asin.encode(), usedforsecurity=False).hexdigest(), 16) % (2**32)
        rng = random.Random(seed)
        price_aed = round(rng.uniform(10.0, 1000.0), 2)
        return CompetitorPrice(
            asin=asin,
            price_aed=price_aed,
            currency="AED",
            marketplace_id=_MARKETPLACE_ID,
            fetched_at=datetime.now(UTC),
            source="stub",
        )

    async def health_check(self) -> dict[str, Any]:
        return {"healthy": True, "source": "stub"}


# Verificación estática que cumple el protocolo
_: FetcherPort = AmazonSPFetcherStub()  # type: ignore[assignment]

__all__ = ["AmazonSPFetcherStub"]
