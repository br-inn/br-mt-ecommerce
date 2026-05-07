"""PMO event bus — abstracciones Fase 2 (US-RND-01-12).

Patrón: ports & adapters. El core publica eventos vía `PmoEventPublisherPort`;
los adapters concretos (Redis pub/sub stub, BR PMO webhook real Fase 2) viven
en `adapters/`.

En Sprint 5 sólo entregamos:
- `PmoEventPublisherPort` (Protocol)
- `RedisPubSubStubPublisher` (mockeable, no conecta Redis real en tests)
- `PmoEventEmitter` con whitelist de eventos auditables
"""

from app.services.pmo_bus.event_emitter import PMO_EVENT_WHITELIST, PmoEventEmitter
from app.services.pmo_bus.ports import PmoEvent, PmoEventPublisherPort

__all__ = [
    "PMO_EVENT_WHITELIST",
    "PmoEvent",
    "PmoEventEmitter",
    "PmoEventPublisherPort",
]
