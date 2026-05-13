"""Tasks de inventario — queue `default`.

Task ``mt.inventory.recalc_map_on_gr``:
  Procesa un Goods Receipt, calcula el nuevo MAP y actualiza la posición
  de inventario, el CostLot y el Cost (scheme_landed_aed).
  Al finalizar, dispara ``recalculate_sku_task`` si está disponible.
"""

from __future__ import annotations

import asyncio
import logging
import traceback
from typing import Any
from uuid import UUID

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:  # noqa: ANN401
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            raise RuntimeError("event loop already running in Celery context")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=30,
    name="mt.inventory.recalc_map_on_gr",
    queue="default",
)
def recalc_map_on_gr(self, gr_id: str) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Procesa un GoodsReceipt y recalcula el MAP del SKU.

    :param gr_id: UUID del GoodsReceipt a procesar.
    :return: dict con gr_id, map_after, sku.
    """

    async def _run() -> dict[str, Any]:
        import dataclasses

        from app.core.config import settings
        from app.db.engine import get_sessionmaker
        from app.services.inventory.map_service import MAPService

        sync_event_id: str | None = None

        async with get_sessionmaker()() as session:
            svc = MAPService(session)
            try:
                pos = await svc.process_gr(UUID(gr_id))

                # Outbox pattern (US-INV-01-07): crear ERPSyncEvent dentro de la
                # misma transacción. Si el commit falla, el evento no existe.
                try:
                    from decimal import Decimal as _Decimal

                    from app.db.models.inventory import ERPSyncEvent, GoodsReceipt
                    from app.integrations.erp.events import GoodsReceivedEvent

                    # Recargar el GR (process_gr lo modificó; seguimos en la misma sesión)
                    gr = await session.get(GoodsReceipt, UUID(gr_id))
                    if gr is not None:
                        # Intentar obtener po_number via relación (puede ser None si no cargada)
                        po_number = ""
                        try:
                            pol = await session.get(
                                __import__("app.db.models.inventory", fromlist=["PurchaseOrderLine"]).PurchaseOrderLine,
                                gr.po_line_id,
                            )
                            if pol is not None:
                                po = await session.get(
                                    __import__("app.db.models.inventory", fromlist=["PurchaseOrder"]).PurchaseOrder,
                                    pol.po_id,
                                )
                                po_number = po.po_number if po is not None else ""
                        except Exception:  # noqa: BLE001
                            pass

                        gr_event = GoodsReceivedEvent(
                            gr_id=gr_id,
                            po_number=po_number,
                            sku=pos.sku,
                            supplier_code=pos.supplier_code,
                            scheme_code=pos.scheme_code,
                            qty_received=gr.qty_received,
                            actual_unit_price=gr.actual_unit_price or _Decimal("0"),
                            actual_breakdown=gr.actual_breakdown or {},
                            map_before=gr.map_before,
                            map_after=pos.map_aed,
                            received_at=gr.received_at,
                            mt_system_ref=f"MT-GR-{gr_id[:8]}",
                        )
                        sync_event = ERPSyncEvent(
                            event_type="goods_received",
                            entity_id=gr_id,
                            payload=dataclasses.asdict(gr_event),
                            adapter=settings.ERP_ADAPTER,
                        )
                        session.add(sync_event)
                        await session.flush()
                        sync_event_id = str(sync_event.id)
                except Exception:  # noqa: BLE001
                    logger.warning(
                        "recalc_map_on_gr: could not create ERPSyncEvent for gr_id=%s",
                        gr_id,
                        exc_info=True,
                    )

                await session.commit()
            except Exception:
                await session.rollback()
                await _mark_gr_error(gr_id, traceback.format_exc())
                raise

        return {
            "gr_id": gr_id,
            "map_after": str(pos.map_aed),
            "sku": pos.sku,
            "erp_sync_event_id": sync_event_id,
        }

    result = _run_async(_run())

    sku = result.get("sku")
    if sku:
        _dispatch_price_recalc(sku)

    sync_event_id = result.get("erp_sync_event_id")
    if sync_event_id:
        _dispatch_erp_event_by_id(sync_event_id)

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _dispatch_price_recalc(sku: str) -> None:
    try:
        from app.workers.tasks.pricing import recalculate_sku_task

        recalculate_sku_task.delay(sku, "system")
        logger.info("recalc_map_on_gr: dispatched recalculate_sku_task sku=%s", sku)
    except Exception:  # noqa: BLE001
        logger.warning(
            "recalc_map_on_gr: could not dispatch recalculate_sku_task for sku=%s",
            sku,
            exc_info=True,
        )


def _dispatch_erp_event_by_id(event_id: str) -> None:
    """Encola push_erp_event con el ID del ERPSyncEvent ya creado en DB."""
    try:
        from app.workers.tasks.erp_sync import push_erp_event

        push_erp_event.delay(event_id)
        logger.info("recalc_map_on_gr: dispatched push_erp_event event_id=%s", event_id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "recalc_map_on_gr: push_erp_event dispatch failed event_id=%s",
            event_id,
            exc_info=True,
        )


async def _mark_gr_error(gr_id: str, tb: str) -> None:
    try:
        from app.db.engine import get_sessionmaker
        from app.db.models.inventory import GoodsReceipt

        async with get_sessionmaker()() as session:
            gr = await session.get(GoodsReceipt, UUID(gr_id))
            if gr is not None:
                gr.status = "error"
                gr.notes = tb[:4000]
                await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception("recalc_map_on_gr: could not mark gr %s as error", gr_id)


__all__ = ["recalc_map_on_gr"]
