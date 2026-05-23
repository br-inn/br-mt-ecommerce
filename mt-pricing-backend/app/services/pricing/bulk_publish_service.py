"""BulkPublishService — publica un lote de precios `approved` → `exported` (Sprint 4 / US-1B-01-04).

Encadena ``PricingService.export`` para cada ``price_id`` con audit + rollback
soft. Diferencia con ``bulk_approve``:

- **bulk_approve**: ``pending_review`` → ``approved``.
- **bulk_publish**: ``approved`` → ``exported`` (terminal). Ojo: estado
  ``exported`` no se puede revertir (FSM); por eso si el "queue" externo
  rechaza la publicación, hacemos audit ``price.publish_failed`` (sin tocar el
  estado, dado que ya quedó marcado como exported localmente).

API:
- ``BulkPublishService(session, pricing_service=None, queue_publisher=None)``.
- ``await svc.publish(price_ids: list[UUID], actor: User) -> BulkPublishResult``.

Si ``queue_publisher`` está presente y devuelve ``False`` para un id, el
service registra audit ``price.publish_queue_failed`` con detalles, pero
mantiene el estado local; el counter ``queue_failed`` se incrementa.

Diseñado para ser pequeño y testable sin DB — los tests inyectan un
``pricing_service`` mock y un ``queue_publisher`` callable.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.repositories.audit import AuditRepository
from app.services.pricing.pricing_service import (
    PricingDomainError,
    PricingService,
)

logger = logging.getLogger(__name__)


QueuePublisher = Callable[[UUID], Awaitable[bool]]


class PricingServiceProtocol(Protocol):
    async def export(self, price_id: UUID, actor: User) -> Any: ...


@dataclass(slots=True)
class BulkPublishResult:
    total: int
    published: list[str] = field(default_factory=list)
    queue_failed: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    rolled_back: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "published": list(self.published),
            "published_count": len(self.published),
            "queue_failed": list(self.queue_failed),
            "errors": list(self.errors),
            "rolled_back": self.rolled_back,
        }


class BulkPublishService:
    """Publica precios en lote con auditoría + rollback soft.

    Si ``rollback_on_error=True`` y ocurre cualquier ``PricingDomainError`` no
    recuperable, deja constancia en audit y marca ``rolled_back=True`` (no
    intenta UPDATE inverso — la FSM de ``exported`` es terminal y el rollback
    real lo hace la session del caller con savepoint si lo necesitase).
    """

    def __init__(
        self,
        session: AsyncSession,
        *,
        pricing_service: PricingServiceProtocol | None = None,
        queue_publisher: QueuePublisher | None = None,
    ) -> None:
        self.session = session
        self.pricing_service: PricingServiceProtocol = pricing_service or PricingService(session)
        self.queue_publisher = queue_publisher
        self.audit = AuditRepository(session)

    async def publish(
        self,
        price_ids: Sequence[UUID],
        actor: User,
        *,
        rollback_on_error: bool = False,
    ) -> BulkPublishResult:
        result = BulkPublishResult(total=len(price_ids))
        if not price_ids:
            return result

        for pid in price_ids:
            try:
                price = await self.pricing_service.export(pid, actor)
            except PricingDomainError as exc:
                logger.warning("bulk_publish: domain error price_id=%s code=%s", pid, exc.code)
                result.errors.append(
                    {
                        "price_id": str(pid),
                        "code": exc.code,
                        "message": exc.message,
                    }
                )
                if rollback_on_error:
                    result.rolled_back = True
                    await self.audit.record(
                        entity_type="price_batch",
                        entity_id=str(pid),
                        action="price.bulk_publish_rolled_back",
                        actor_id=actor.id,
                        actor_email=actor.email,
                        payload_diff={
                            "errors_count": len(result.errors),
                            "first_error": exc.code,
                        },
                    )
                    return result
                continue
            except Exception as exc:
                logger.exception("bulk_publish: unexpected error price_id=%s", pid)
                result.errors.append(
                    {
                        "price_id": str(pid),
                        "code": "internal_error",
                        "message": f"{type(exc).__name__}: {exc!s}",
                    }
                )
                if rollback_on_error:
                    result.rolled_back = True
                    return result
                continue

            # Publicación a la cola externa (opcional)
            if self.queue_publisher is not None:
                try:
                    accepted = await self.queue_publisher(price.id)
                except Exception as exc:
                    accepted = False
                    logger.exception("bulk_publish: queue publisher raised price_id=%s", price.id)
                    await self.audit.record(
                        entity_type="price",
                        entity_id=str(price.id),
                        action="price.publish_queue_error",
                        actor_id=actor.id,
                        actor_email=actor.email,
                        payload_diff={"error": f"{type(exc).__name__}: {exc!s}"},
                    )
                    result.queue_failed.append(
                        {"price_id": str(price.id), "reason": "queue_exception"}
                    )
                    continue

                if not accepted:
                    await self.audit.record(
                        entity_type="price",
                        entity_id=str(price.id),
                        action="price.publish_queue_failed",
                        actor_id=actor.id,
                        actor_email=actor.email,
                        payload_diff={"reason": "queue_rejected"},
                    )
                    result.queue_failed.append(
                        {"price_id": str(price.id), "reason": "queue_rejected"}
                    )
                    continue

            result.published.append(str(price.id))

        await self.audit.record(
            entity_type="price_batch",
            entity_id="bulk_publish",
            action="price.bulk_published",
            actor_id=actor.id,
            actor_email=actor.email,
            payload_diff={
                "total": result.total,
                "published": len(result.published),
                "queue_failed": len(result.queue_failed),
                "errors": len(result.errors),
            },
        )
        return result


__all__ = ["BulkPublishResult", "BulkPublishService", "PricingServiceProtocol"]
