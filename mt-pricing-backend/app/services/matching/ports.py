"""Hexagonal ports for the matching pipeline.

Define el contrato que cualquier fetcher (Bright Data, Playwright, stub)
debe cumplir. La capa de servicio (`MatchService`) sólo depende de estos
protocolos — los adapters concretos viven en ``adapters/``.

Pipeline doc reference: §4 (Multi-Source Fetcher), §3.5 (Query Builder).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any, Protocol


# ---------------------------------------------------------------------------
# Channels supported by Sprint 3 foundation
# ---------------------------------------------------------------------------
SUPPORTED_CHANNELS: tuple[str, ...] = ("amazon_uae", "noon_uae")


@dataclass(frozen=True)
class Query:
    """Una query elaborada por el Query Builder (Etapa 1)."""

    text: str
    source: str
    lang: str = "en"
    type: str = "spec"
    dept: str = "industrial"
    category_node: str | None = None


@dataclass
class CandidateRaw:
    """Resultado crudo devuelto por un fetcher (Etapa 2 output).

    Las specs estructuradas se persisten más tarde en
    ``match_candidates.specs_jsonb``; los stubs ya devuelven un dict canónico
    con material/valve_type/thread/pn/norma cuando es posible.
    """

    source: str
    external_id: str
    title: str
    brand: str | None = None
    price_aed: Decimal | None = None
    delivery_text: str | None = None
    specs: dict[str, Any] = field(default_factory=dict)
    raw_payload: dict[str, Any] = field(default_factory=dict)
    fetched_at: datetime | None = None


class FetcherPort(Protocol):
    """Puerto del fetcher — un adapter por canal/marketplace.

    Implementaciones reales (Bright Data, Playwright) reciben el query, hacen
    la llamada al scraper y devuelven una lista de ``CandidateRaw``. Los stubs
    devuelven datos canned por SKU para Sprint 3.
    """

    @property
    def channel(self) -> str:
        """Canal soportado (ej. ``amazon_uae`` o ``noon_uae``)."""
        ...

    async def fetch(self, query: Query, *, sku: str | None = None) -> list[CandidateRaw]:
        """Devuelve candidatos crudos para una query (puede ignorar sku).

        Stubs lo usan para devolver listas determinísticas por SKU.
        """
        ...
