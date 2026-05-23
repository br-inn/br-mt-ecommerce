"""Hexagonal port — contrato común para adapters de canal externo.

Cada canal (Amazon SP-API, Noon API, futuros) implementa ``ChannelMirrorPort``
y se inyecta en ``MirrorService``. Esto permite:

- Tests unitarios usando un fake adapter (no requiere HTTP).
- Swap a implementación real (Sprint 4+) sin tocar el orchestrator ni los routes.
- Agregar canales nuevos (B2B, marketplaces extra) sin duplicar código.

Sprint 3 usa stubs (``adapters/amazon_sp_api_stub.py``, ``noon_api_stub.py``)
que devuelven payload canned.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal, Protocol

BuyBoxState = Literal["own", "competitor", "none"]


@dataclass(frozen=True)
class LiveListing:
    """Snapshot del listing tal como lo expone el canal externo.

    Es lo que devuelve un ``pull()``. Mantenemos el shape genérico para que
    encaje con cualquier marketplace; el ``raw`` JSONB carga la respuesta
    completa para auditoría / debugging.
    """

    channel_code: str
    external_id: str  # ASIN, Noon SKU, etc.
    sku: str
    fields: dict[str, Any]  # {title_en, title_ar, bullet_1, ..., price_aed, ...}
    buybox_state: BuyBoxState = "none"
    buybox_pct_7d: float | None = None
    stock_qty: int | None = None
    rating: float | None = None
    reviews_count: int | None = None
    fetched_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class PublishResult:
    """Resultado de un intento de push hacia el canal externo."""

    ok: bool
    submission_id: str | None = None
    accepted_fields: list[str] = field(default_factory=list)
    rejected_fields: list[str] = field(default_factory=list)
    message: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class ChannelMirrorPort(Protocol):
    """Contrato que cada adapter de canal debe cumplir."""

    channel_code: str  # 'amazon_uae', 'noon_uae', ...

    async def pull_listing(self, sku: str, external_id: str | None = None) -> LiveListing:
        """Lee el listing live desde el canal externo.

        Sprint 3: stub devuelve canned data hardcodeada.
        Sprint 4+: HTTP real con throttling + retries.

        Si el SKU no existe en el canal, devuelve ``LiveListing`` con
        ``fields={}`` y ``external_id=""`` — el diff engine lo marcará como
        ``missing`` para todos los campos canonical.
        """
        ...

    async def push_diff(
        self,
        sku: str,
        external_id: str | None,
        diff_payload: dict[str, Any],
    ) -> PublishResult:
        """Empuja diferencias al canal externo.

        Sprint 3: stub que solo persiste el intento (no HTTP).
        Sprint 4+: SP-API submitListings / Noon partner API real.
        """
        ...
