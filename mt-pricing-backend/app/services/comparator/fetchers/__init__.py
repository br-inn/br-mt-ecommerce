"""FetcherPort protocol + CompetitorPrice dataclass — US-F15-02-01.

Contrato que deben implementar todos los adapters de fetching de precios
de competidores (Amazon SP API real, stub, futuros: Noon, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol, runtime_checkable


@dataclass
class CompetitorPrice:
    asin: str
    price_aed: float
    currency: str
    marketplace_id: str
    fetched_at: datetime
    source: str  # "amazon_sp_api" o "stub"


@runtime_checkable
class FetcherPort(Protocol):
    async def fetch_competitor_price(self, asin: str) -> CompetitorPrice: ...
    async def health_check(self) -> dict[str, Any]: ...


__all__ = ["CompetitorPrice", "FetcherPort"]
