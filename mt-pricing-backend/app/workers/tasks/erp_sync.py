"""Celery task: push_erp_event — outbox processor (US-INV-01-07).

Consume filas de ``erp_sync_events`` con ``status='pending'``, llama al
adapter ERP configurado y actualiza el estado de la fila.

Reintentos exponenciales:
  - countdown = 60 * 2^attempts (60s, 120s, 240s, 480s, 960s)
  - Tras 5 intentos fallidos: status='failed', sin más retries

Firma HMAC-256:
  Si ``ERP_WEBHOOK_SECRET`` está definido, se firma el payload con
  ``hmac(secret, json.dumps(payload, sort_keys=True))`` y se logea en
  DEBUG (preparado para adapters HTTP futuros que envíen el header
  ``X-MT-Signature: sha256={hex}``).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)

_MAX_RETRIES = 5


def _run_async(coro: Any) -> Any:  # noqa: ANN401
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("event loop already running in Celery context")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


async def _process_event(event_id: str, task_self: Any) -> dict[str, Any]:
    """Núcleo del procesamiento — extraído para facilitar tests.

    Importa dependencias localmente para evitar import circular en el worker.
    """
    from app.core.config import settings
    from app.db.engine import get_sessionmaker
    from app.db.models.inventory import ERPSyncEvent
    from app.integrations.erp.events import GoodsReceivedEvent, MAPUpdatedEvent
    from app.integrations.erp.factory import get_erp_adapter

    async with get_sessionmaker()() as session:
        event = await session.get(ERPSyncEvent, UUID(event_id))
        if event is None:
            logger.error("push_erp_event: event not found id=%s", event_id)
            return {"event_id": event_id, "status": "not_found"}

        # Idempotencia — si ya fue procesado, no hacer nada
        if event.status != "pending":
            logger.info(
                "push_erp_event: already processed id=%s status=%s — skip",
                event_id,
                event.status,
            )
            return {"event_id": event_id, "status": event.status}

        # Con adapter noop, marcar skipped inmediatamente — sin ruido en fallos
        if settings.ERP_ADAPTER.lower() == "noop":
            # HMAC se computa de todas formas si hay secret (para logs)
            payload_dict: dict = event.payload or {}
            if settings.ERP_WEBHOOK_SECRET:
                signature_hex = hmac.new(
                    settings.ERP_WEBHOOK_SECRET.encode(),
                    json.dumps(payload_dict, sort_keys=True, default=str).encode(),
                    hashlib.sha256,
                ).hexdigest()
                logger.debug(
                    "push_erp_event: X-MT-Signature sha256=%s id=%s",
                    signature_hex,
                    event_id,
                )
            event.status = "skipped"
            await session.commit()
            logger.info("push_erp_event: adapter=noop — marked skipped id=%s", event_id)
            return {"event_id": event_id, "status": "skipped"}

        # HMAC-256 — firmar payload (preparado para adapters HTTP futuros)
        payload_dict = event.payload or {}
        if settings.ERP_WEBHOOK_SECRET:
            signature_hex = hmac.new(
                settings.ERP_WEBHOOK_SECRET.encode(),
                json.dumps(payload_dict, sort_keys=True, default=str).encode(),
                hashlib.sha256,
            ).hexdigest()
            logger.debug(
                "push_erp_event: X-MT-Signature sha256=%s id=%s",
                signature_hex,
                event_id,
            )

        adapter = get_erp_adapter()

        try:
            if event.event_type == "goods_received":
                typed_event = GoodsReceivedEvent(**payload_dict)
                external_ref: str | None = await adapter.push_goods_receipt(typed_event)
            elif event.event_type == "map_updated":
                typed_event = MAPUpdatedEvent(**payload_dict)  # type: ignore[assignment]
                await adapter.push_map_update(typed_event)
                external_ref = None
            else:
                logger.warning(
                    "push_erp_event: unknown event_type=%s id=%s — skipping",
                    event.event_type,
                    event_id,
                )
                event.status = "skipped"
                await session.commit()
                return {"event_id": event_id, "status": "skipped"}

            event.status = "delivered"
            event.delivered_at = datetime.now(UTC)
            if external_ref:
                event.external_ref = external_ref
            await session.commit()
            logger.info(
                "push_erp_event: delivered id=%s external_ref=%s",
                event_id,
                external_ref,
            )
            return {
                "event_id": event_id,
                "status": "delivered",
                "external_ref": external_ref,
            }

        except Exception as exc:
            await session.rollback()

            # Recargar la fila para aplicar el update de intentos limpiamente
            event = await session.get(ERPSyncEvent, UUID(event_id))
            if event is None:
                raise

            event.attempts = (event.attempts or 0) + 1
            event.last_attempted_at = datetime.now(UTC)
            event.last_error = str(exc)[:4000]

            if event.attempts >= _MAX_RETRIES:
                event.status = "failed"
                await session.commit()
                logger.error(
                    "push_erp_event: max retries reached — failed id=%s attempts=%d error=%s",
                    event_id,
                    event.attempts,
                    exc,
                )
                return {"event_id": event_id, "status": "failed"}

            await session.commit()

            countdown = 60 * (2 ** event.attempts)
            logger.warning(
                "push_erp_event: attempt %d failed — retry in %ds id=%s error=%s",
                event.attempts,
                countdown,
                event_id,
                exc,
            )
            raise task_self.retry(exc=exc, countdown=countdown)


@celery_app.task(
    bind=True,
    name="mt.erp.push_erp_event",
    queue="default",
    max_retries=_MAX_RETRIES,
)
def push_erp_event(self, event_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Procesa un ERPSyncEvent y lo envía al adapter ERP configurado.

    :param event_id: UUID del ``ERPSyncEvent`` a procesar.
    :return: dict con ``event_id``, ``status`` y opcionalmente ``external_ref``.
    """
    return _run_async(_process_event(event_id, self))


__all__ = ["push_erp_event", "_process_event"]
