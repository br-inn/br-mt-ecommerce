"""Hexagonal port — contrato para exportación de precios aprobados hacia canales.

``ChannelPublisher`` define la interfaz que cada adapter debe cumplir. Los
adapters skeleton (Sprint 8) devuelven respuestas canned; Sprint 9+ implementa
la integración real con cada marketplace.

Canales soportados en esta iteración:
- ``AMAZON_UAE``  — Amazon SP-API UAE
- ``NOON_UAE``    — Noon Partner API UAE
- ``SHOPIFY``     — Shopify Plus / Hydrogen

Uso típico (US-1B-04-02, endpoint exports)::

    adapter = AmazonUAEAdapter()
    errors  = adapter.validate_payload(payload)
    if not errors:
        csv_bytes, result = await adapter.export_csv(payload)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol


# ---------------------------------------------------------------------------
# Value objects
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class PublishPayload:
    """Datos de entrada para una exportación de precios.

    ``rows`` es una lista de dicts con keys esperados:
    ``{sku, price_aed, status, fx_rate, approved_at}``.
    """

    channel_code: str          # 'AMAZON_UAE', 'NOON_UAE', 'SHOPIFY'
    scheme_code: str           # 'FBA', 'MARKETPLACE', etc.
    rows: list[dict]           # cada dict: {sku, price_aed, status, fx_rate, approved_at}
    generated_at: datetime
    fx_as_of: datetime | None = None


@dataclass(frozen=True)
class ExportResult:
    """Resultado de un intento de exportación de precios hacia un canal."""

    ok: bool
    channel_code: str
    rows_exported: int
    rows_blocked: int          # filas excluidas por estado no aprobado
    submission_id: str | None = None
    errors: list[dict] = field(default_factory=list)  # [{field, row, code, message}]
    shadow_mode: bool = False
    exported_at: datetime | None = None
    raw: dict = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Protocol (port)
# ---------------------------------------------------------------------------

class ChannelPublisher(Protocol):
    """Contrato que cada adapter de exportación de precios debe cumplir.

    Arquitectura hexagonal: el servicio orquestador (US-1B-04-02) recibe una
    instancia de ``ChannelPublisher`` por inyección de dependencias. Para
    tests, se puede sustituir por un fake sin modificar nada fuera del bind.
    """

    channel_code: str  # 'AMAZON_UAE', 'NOON_UAE', 'SHOPIFY'

    def validate_payload(self, payload: PublishPayload) -> list[dict]:
        """Valida el payload y retorna lista de errores ``[{field, row, code, message}]``.

        Lista vacía = payload válido.
        No tiene side-effects; puede llamarse varias veces.
        """
        ...

    async def shadow_publish(self, payload: PublishPayload) -> ExportResult:
        """Envía a sandbox/staging del canal y captura respuesta.

        No modifica producción. ``shadow_mode=True`` en el resultado.
        Sprint 8: stub; Sprint 9+: llamada real al sandbox del marketplace.
        """
        ...

    async def export_csv(self, payload: PublishPayload) -> tuple[bytes, ExportResult]:
        """Genera CSV/XLSX en bytes listo para descarga + metadatos del export.

        Retorna ``(file_bytes, ExportResult)`` donde ``file_bytes`` es el
        contenido del archivo (CSV o XLSX según el adapter).
        """
        ...
