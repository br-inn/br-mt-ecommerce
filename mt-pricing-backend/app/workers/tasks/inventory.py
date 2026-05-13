"""Tasks de inventario — queue `default`.

Task ``mt.inventory.recalc_map_on_gr``:
  Procesa un Goods Receipt, calcula el nuevo MAP y actualiza la posición
  de inventario, el CostLot y el Cost (scheme_landed_aed).
  Al finalizar, dispara ``recalculate_sku_task`` si está disponible.

Task ``mt.inventory.check_lot_expiry_warnings`` (US-ERP-02-05):
  Detecta lotes con expiry_date < today + threshold_days y crea
  InventoryAlerts de tipo LOT_EXPIRY_WARNING. Cron: 0 6 * * *

Task ``mt.inventory.run_rop_check`` (US-ERP-02-06):
  Para cada producto activo, si qty_on_hand <= reorder_point crea
  una PurchaseRequisition automática con status='pending_approval'.
  Cron: 0 7 * * *

Task ``mt.inventory.run_abc_classification`` (US-ERP-02-07):
  Clasifica productos A/B/C por annual_consumption_value.
  Cron: 0 2 1 * * (1ro de cada mes)
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


__all__ = [
    "recalc_map_on_gr",
    "check_lot_expiry_warnings",
    "run_rop_check",
    "run_abc_classification",
]


# ---------------------------------------------------------------------------
# US-ERP-02-05: check_lot_expiry_warnings
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name="mt.inventory.check_lot_expiry_warnings",
    queue="default",
)
def check_lot_expiry_warnings(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Detecta lotes próximos a vencer y crea alertas LOT_EXPIRY_WARNING.

    Umbral por producto en expiry_alert_thresholds (default 30 días).
    Idempotente: no duplica alertas activas para el mismo lote.
    """

    async def _run() -> dict[str, Any]:
        from datetime import date, timedelta

        from sqlalchemy import func, select, text

        from app.db.engine import get_sessionmaker
        from app.db.models.inventory import (
            ExpiryAlertThreshold,
            InventoryAlert,
            InventoryLot,
            InventoryPosition,
        )

        async with get_sessionmaker()() as session:
            today = date.today()
            default_threshold = 30

            # Cargar umbrales configurados
            threshold_rows = await session.execute(
                select(ExpiryAlertThreshold)
            )
            thresholds: dict[str, int] = {
                t.product_sku: t.threshold_days
                for t in threshold_rows.scalars().all()
            }

            # Lotes con expiry_date próxima (usando threshold por defecto o específico)
            lots_q = await session.execute(
                select(InventoryLot).where(
                    InventoryLot.expiry_date.is_not(None),
                    InventoryLot.quality_status == "released",
                )
            )
            lots = lots_q.scalars().all()

            alerts_created = 0
            lot_ids_warned: list[str] = []

            for lot in lots:
                thresh = thresholds.get(lot.product_sku, default_threshold)
                if lot.expiry_date is None:
                    continue
                days_left = (lot.expiry_date - today).days
                if days_left > thresh:
                    continue

                # Comprobar si ya existe una alerta activa para este lote
                existing = await session.execute(
                    select(InventoryAlert).where(
                        InventoryAlert.lot_id == lot.id,
                        InventoryAlert.alert_type == "LOT_EXPIRY_WARNING",
                        InventoryAlert.resolved_at.is_(None),
                    )
                )
                if existing.scalars().first() is not None:
                    continue

                # Obtener qty_on_hand (primera posición con este lote)
                pos_q = await session.execute(
                    select(InventoryPosition).where(
                        InventoryPosition.lot_id == lot.id,
                        InventoryPosition.stock_type == "unrestricted",
                    ).limit(1)
                )
                pos = pos_q.scalars().first()
                qty_on_hand = float(pos.qty_on_hand) if pos else 0.0

                severity = "critical" if days_left <= 7 else "warning"
                alert = InventoryAlert(
                    alert_type="LOT_EXPIRY_WARNING",
                    product_sku=lot.product_sku,
                    lot_id=lot.id,
                    warehouse_id=pos.warehouse_id if pos else None,
                    severity=severity,
                    payload={
                        "lot_number": lot.lot_number,
                        "expiry_date": lot.expiry_date.isoformat(),
                        "days_until_expiry": days_left,
                        "qty_on_hand": qty_on_hand,
                        "threshold_days": thresh,
                    },
                )
                session.add(alert)
                alerts_created += 1
                lot_ids_warned.append(str(lot.id))

            await session.commit()
            return {"alerts_created": alerts_created, "lot_ids": lot_ids_warned}

    return _run_async(_run())


# ---------------------------------------------------------------------------
# US-ERP-02-06: run_rop_check
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=60,
    name="mt.inventory.run_rop_check",
    queue="default",
)
def run_rop_check(self) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Job ROP diario: crea PurchaseRequisitions automáticas cuando qty_on_hand <= reorder_point."""

    async def _run() -> dict[str, Any]:
        import datetime as _dt
        from decimal import Decimal

        from sqlalchemy import func, select

        from app.db.engine import get_sessionmaker
        from app.db.models.inventory import InventoryPosition, ReplenishmentParam
        from app.db.models.procurement import PurchaseRequisition

        async with get_sessionmaker()() as session:
            # Obtener posiciones unrestricted con ROP activo
            rp_q = await session.execute(
                select(ReplenishmentParam).where(
                    ReplenishmentParam.is_active.is_(True)
                )
            )
            params = rp_q.scalars().all()

            prs_created = 0
            sku_breaches: list[str] = []

            for rp in params:
                # Suma de qty_on_hand en el almacén para el SKU
                qty_q = await session.execute(
                    select(func.coalesce(func.sum(InventoryPosition.qty_on_hand), Decimal("0"))).where(
                        InventoryPosition.sku == rp.product_sku,
                        InventoryPosition.warehouse_id == rp.warehouse_id,
                        InventoryPosition.stock_type == "unrestricted",
                    )
                )
                qty_on_hand: Decimal = qty_q.scalar() or Decimal("0")

                if qty_on_hand > rp.reorder_point:
                    continue

                # Evitar duplicar PRs auto-ROP activas para este SKU × almacén
                existing_pr = await session.execute(
                    select(PurchaseRequisition).where(
                        PurchaseRequisition.product_sku == rp.product_sku,
                        PurchaseRequisition.status == "pending_approval",
                        PurchaseRequisition.notes.like("Auto-ROP%"),
                    ).limit(1)
                )
                if existing_pr.scalars().first() is not None:
                    continue

                # Número secuencial simple: PR-ROP-YYYYMMDD-<sku>
                today_str = _dt.date.today().strftime("%Y%m%d")
                pr_number = f"PR-ROP-{today_str}-{rp.product_sku[:20]}"

                # Necesita un requester; usar sistema UUID cero (pseudo-system user)
                from uuid import UUID as _UUID
                system_user_id = _UUID("00000000-0000-0000-0000-000000000001")

                pr = PurchaseRequisition(
                    pr_number=pr_number,
                    requester_id=system_user_id,
                    product_sku=rp.product_sku,
                    qty_requested=rp.reorder_qty,
                    status="pending_approval",
                    notes=f"Auto-ROP: qty_on_hand={qty_on_hand} <= reorder_point={rp.reorder_point} (wh={rp.warehouse_id})",
                )
                session.add(pr)
                prs_created += 1
                sku_breaches.append(rp.product_sku)

            await session.commit()
            return {"prs_created": prs_created, "sku_breaches": sku_breaches}

    return _run_async(_run())


# ---------------------------------------------------------------------------
# US-ERP-02-07: run_abc_classification
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    max_retries=3,
    default_retry_delay=120,
    name="mt.inventory.run_abc_classification",
    queue="default",
)
def run_abc_classification(self, warehouse_id: str | None = None) -> dict[str, Any]:  # type: ignore[no-untyped-def]
    """Clasificación ABC mensual por annual_consumption_value DESC.

    Criterios: A=80%, B=15%, C=5% (acumulado).
    Hace UPSERT en product_abc_classifications.
    """

    async def _run() -> dict[str, Any]:
        import datetime as _dt
        from decimal import Decimal
        from uuid import UUID as _UUID

        from sqlalchemy import func, select
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from app.db.engine import get_sessionmaker
        from app.db.models.inventory import (
            InventoryPosition,
            ProductAbcClassification,
            Warehouse,
        )

        async with get_sessionmaker()() as session:
            # Determinar almacenes a procesar
            if warehouse_id:
                wh_ids: list[_UUID] = [_UUID(warehouse_id)]
            else:
                wh_q = await session.execute(
                    select(Warehouse.id).where(Warehouse.is_active.is_(True))
                )
                wh_ids = list(wh_q.scalars().all())

            total_classified = 0
            class_counts = {"A": 0, "B": 0, "C": 0}

            for wh_id in wh_ids:
                # Calcular annual_consumption_value: sum(qty_on_hand * map_aed) * 12
                # (proxy: posición actual × MAP × 12 meses)
                pos_q = await session.execute(
                    select(
                        InventoryPosition.sku,
                        func.sum(
                            InventoryPosition.qty_on_hand * func.coalesce(InventoryPosition.map_aed, Decimal("0"))
                        ).label("consumption_value"),
                    ).where(
                        InventoryPosition.warehouse_id == wh_id,
                        InventoryPosition.stock_type == "unrestricted",
                    ).group_by(InventoryPosition.sku)
                    .order_by(func.sum(
                        InventoryPosition.qty_on_hand * func.coalesce(InventoryPosition.map_aed, Decimal("0"))
                    ).desc())
                )
                rows = pos_q.all()
                if not rows:
                    continue

                total_value = sum(r.consumption_value or Decimal("0") for r in rows)
                if total_value == 0:
                    continue

                # Asignar clases ABC acumulativas
                cumulative = Decimal("0")
                classified_at = _dt.datetime.now(tz=_dt.timezone.utc)

                for row in rows:
                    val = row.consumption_value or Decimal("0")
                    annual_val = val * 12
                    pct = (val / total_value * 100) if total_value else Decimal("0")
                    cumulative += pct

                    if cumulative <= 80:
                        abc = "A"
                    elif cumulative <= 95:
                        abc = "B"
                    else:
                        abc = "C"

                    # UPSERT via SQLAlchemy core
                    stmt = pg_insert(ProductAbcClassification.__table__).values(
                        id=func.gen_random_uuid(),
                        product_sku=row.sku,
                        warehouse_id=wh_id,
                        abc_class=abc,
                        annual_consumption_value=annual_val,
                        pct_of_total=pct,
                        classified_at=classified_at,
                    ).on_conflict_do_update(
                        constraint="uq_abc_sku_wh",
                        set_={
                            "abc_class": abc,
                            "annual_consumption_value": annual_val,
                            "pct_of_total": pct,
                            "classified_at": classified_at,
                        },
                    )
                    await session.execute(stmt)
                    class_counts[abc] += 1
                    total_classified += 1

            await session.commit()
            return {
                "warehouse_id": warehouse_id,
                "products_classified": total_classified,
                "class_a_count": class_counts["A"],
                "class_b_count": class_counts["B"],
                "class_c_count": class_counts["C"],
            }

    return _run_async(_run())
