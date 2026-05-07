"""Ports — interfaces puras para el bus PMO. Sin deps externas."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True, slots=True)
class PmoEvent:
    """Evento serializable enviado al bus PMO Fase 2.

    Atributos:
        event_name: nombre canónico del evento (whitelist en `event_emitter`).
        payload: datos opacos serializables JSON. Sin PII.
        emitted_at: timestamp UTC (ISO 8601 al serializar).
        source: identificador del componente emisor (e.g. "mt-pricing-backend").
        correlation_id: trace_id activo o UUID; permite correlación cross-service.
    """

    event_name: str
    payload: dict[str, Any]
    emitted_at: datetime = field(default_factory=lambda: datetime.now(tz=timezone.utc))
    source: str = "mt-pricing-backend"
    correlation_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_name": self.event_name,
            "payload": self.payload,
            "emitted_at": self.emitted_at.isoformat(),
            "source": self.source,
            "correlation_id": self.correlation_id,
        }


@runtime_checkable
class PmoEventPublisherPort(Protocol):
    """Puerto de publicación. Adapters concretos implementan `publish`."""

    def publish(self, event: PmoEvent) -> None:
        """Publica el evento. Implementaciones DEBEN ser fail-safe — un fallo
        del bus PMO NO debe afectar al flujo principal de negocio.
        """
        ...
