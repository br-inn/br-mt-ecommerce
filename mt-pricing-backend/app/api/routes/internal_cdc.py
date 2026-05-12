"""Endpoint webhook para CDC events (Supabase Realtime → Celery → Neo4j)."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Header, HTTPException, status

from app.core.config import settings
from app.schemas.cdc_event import CdcProductEvent
from app.workers.tasks.graphrag import sync_product_to_kg

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/internal/cdc", tags=["internal-cdc"])


def _verify_internal_secret(x_internal_secret: str | None = Header(default=None)) -> None:
    """Verifica header X-Internal-Secret contra INTERNAL_CDC_SECRET.

    Si el secret no está configurado (vacío), el endpoint acepta cualquier
    request — modo dev/local sin autenticación.
    """
    expected = settings.INTERNAL_CDC_SECRET
    if not expected:
        if x_internal_secret is None:
            logger.warning(
                "cdc.internal_secret.not_configured "
                "— endpoint abierto (dev mode)"
            )
        return
    if x_internal_secret != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal secret",
        )


@router.post("/product", status_code=status.HTTP_202_ACCEPTED)
async def cdc_product_event(
    event: CdcProductEvent,
    _: None = Depends(_verify_internal_secret),
) -> dict:
    """Recibe CDC event de producto y encola sync a Neo4j vía Celery.

    Payload esperado::

        {
            "table": "products",
            "operation": "INSERT",   # INSERT | UPDATE | DELETE
            "record_id": "<uuid>",
            "payload": {}            # opcional — datos extra del row
        }

    Responde 202 inmediatamente; la sincronización ocurre async en Celery.
    Retry automático: 3 intentos con backoff 10 s / 30 s / 90 s.
    """
    event.received_at = datetime.now(UTC)
    logger.info(
        "cdc.product.received table=%s op=%s id=%s",
        event.table,
        event.operation,
        event.record_id,
    )

    sync_product_to_kg.delay(
        product_id=event.record_id,
        operation=event.operation.lower(),
    )
    return {
        "status": "queued",
        "record_id": event.record_id,
        "operation": event.operation,
    }
