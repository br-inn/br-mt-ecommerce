"""Redis pub/sub stub — publica a channel `mt:pmo:events` (US-RND-01-12).

Stub para Fase 2 — *NO* es un bridge BR PMO real. El channel se usa para que un
suscriptor cualquiera (un nuevo servicio Fase 2 o un script de auditoría) pueda
absorber el stream. Si Redis no está disponible o falla, el publish es silencioso
(loggea warning) — fail-safe by design.

Tests mockean `redis_client.publish` — NO necesitan Redis real corriendo.
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Protocol

import structlog

from app.services.pmo_bus.ports import PmoEvent, PmoEventPublisherPort

if TYPE_CHECKING:  # pragma: no cover
    from redis import Redis

logger = structlog.get_logger(__name__)

DEFAULT_CHANNEL = "mt:pmo:events"


class _SyncRedisPublisher(Protocol):
    """Sub-protocolo redis (sync). Mockeable en tests."""

    def publish(self, channel: str, message: str | bytes) -> int: ...


class RedisPubSubStubPublisher(PmoEventPublisherPort):
    """Adapter pub/sub Redis. Cumple `PmoEventPublisherPort`.

    Args:
        redis_client: instancia compatible (`redis.Redis` o mock).
        channel: nombre del channel — default `mt:pmo:events`.
    """

    def __init__(
        self,
        redis_client: _SyncRedisPublisher | Redis,
        channel: str = DEFAULT_CHANNEL,
    ) -> None:
        self._redis = redis_client
        self._channel = channel

    @property
    def channel(self) -> str:
        return self._channel

    def publish(self, event: PmoEvent) -> None:
        """Serializa el evento a JSON y lo publica. Fail-safe: nunca raise."""
        try:
            message = json.dumps(event.to_dict(), default=str)
        except (TypeError, ValueError) as exc:
            logger.warning(
                "pmo_bus.serialize_failed",
                event_name=event.event_name,
                error=str(exc),
            )
            return

        try:
            subscribers = self._redis.publish(self._channel, message)
            logger.debug(
                "pmo_bus.published",
                channel=self._channel,
                event_name=event.event_name,
                subscribers=subscribers,
            )
        except Exception as exc:
            # Redis caído / network error — log + swallow (NFR fail-safe)
            logger.warning(
                "pmo_bus.publish_failed",
                channel=self._channel,
                event_name=event.event_name,
                error=str(exc),
                error_type=type(exc).__name__,
            )
