"""NoOp ERP Adapter — implementación vacía para dev/test.

Todos los métodos loguean la llamada en INFO y retornan valores vacíos/dummy.
No lanza excepciones — seguro como default en entornos sin ERP real conectado.

Si ``settings.ERP_DEBUG = True`` también vuelca el evento serializado como JSON
(útil durante la integración real para inspeccionar el payload exacto).
"""

from __future__ import annotations

import dataclasses
import json
import logging
from datetime import datetime

from app.integrations.erp.adapter import ERPAdapter
from app.integrations.erp.events import GoodsReceivedEvent, MAPUpdatedEvent, POImport

logger = logging.getLogger(__name__)


def _debug_dump(obj: object) -> None:
    """Vuelca el objeto como JSON en DEBUG si ERP_DEBUG está activado."""
    from app.core.config import settings

    if settings.ERP_DEBUG:
        try:
            payload = json.dumps(dataclasses.asdict(obj), default=str)  # type: ignore[arg-type]
        except Exception:
            payload = repr(obj)
        logger.info("[ERP:NoOp] event payload: %s", payload)


class NoOpAdapter(ERPAdapter):
    """Adapter sin efecto — registra llamadas y devuelve valores nulos.

    Nunca lanza excepciones. Es el fallback seguro cuando no hay ERP configurado.
    """

    async def push_goods_receipt(self, event: GoodsReceivedEvent) -> str:
        logger.info("[ERP:NoOp] push_goods_receipt called — adapter is no-op")
        _debug_dump(event)
        return f"noop-ref-{event.gr_id[:8]}"

    async def pull_purchase_orders(self, since: datetime) -> list[POImport]:
        logger.info("[ERP:NoOp] pull_purchase_orders called — adapter is no-op")
        return []

    async def push_map_update(self, event: MAPUpdatedEvent) -> None:
        logger.info("[ERP:NoOp] push_map_update called — adapter is no-op")
        _debug_dump(event)

    async def health_check(self) -> bool:
        logger.info("[ERP:NoOp] health_check called — adapter is no-op")
        return True
