"""Tasks de ventas O2C — queue `default`.

Task ``mt.sales.re_evaluate_backorders``:
  Re-evalúa SO lines en backorder cada 30 minutos.
  Se dispara también desde el worker de GR al procesar una recepción.
  Si el ATP calculado cubre la cantidad, confirma la línea y crea
  stock_reservations.
"""

from __future__ import annotations

import asyncio
import logging
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
    name="mt.sales.re_evaluate_backorders",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def re_evaluate_backorders(self: Any) -> dict[str, Any]:  # noqa: ANN401
    """Re-evalúa SO lines en backorder y confirma reservas cuando hay ATP.

    Cron: cada 30 minutos (configurado en job_definitions).
    """
    return _run_async(_re_evaluate_backorders_async())


async def _re_evaluate_backorders_async() -> dict[str, Any]:
    from sqlalchemy import select

    from app.db import get_db_session
    from app.db.models.sales import (
        SalesOrder,
        SalesOrderLine,
        StockReservation,
    )
    from app.services.atp import compute_atp_for_so

    confirmed_count = 0
    error_count = 0

    async with get_db_session() as db:
        # Find SOs with backorder lines
        stmt = (
            select(SalesOrder)
            .join(SalesOrderLine, SalesOrderLine.so_id == SalesOrder.id)
            .where(
                SalesOrder.status.in_(["confirmed", "in_fulfillment"]),
                SalesOrderLine.status == "open",
            )
            .distinct()
        )
        result = await db.execute(stmt)
        orders = result.scalars().all()

        for so in orders:
            try:
                atp_lines = await compute_atp_for_so(db, so)
                for atp_result in atp_lines:
                    if atp_result.status != "available":
                        continue
                    # Find the SO line
                    sol_stmt = select(SalesOrderLine).where(
                        SalesOrderLine.id == atp_result.so_line_id,
                        SalesOrderLine.status == "open",
                    )
                    sol_res = await db.execute(sol_stmt)
                    sol = sol_res.scalar_one_or_none()
                    if sol is None:
                        continue

                    # Create reservation if not already reserved
                    existing_stmt = select(StockReservation).where(
                        StockReservation.so_line_id == sol.id,
                        StockReservation.status == "active",
                    )
                    existing_res = await db.execute(existing_stmt)
                    if existing_res.scalar_one_or_none():
                        continue

                    if so.warehouse_id is None:
                        continue

                    reservation = StockReservation(
                        so_line_id=sol.id,
                        product_sku=sol.product_sku,
                        warehouse_id=so.warehouse_id,
                        qty=atp_result.atp_qty,
                        status="active",
                    )
                    db.add(reservation)
                    sol.status = "confirmed"
                    sol.confirmed_qty = atp_result.atp_qty
                    confirmed_count += 1

            except Exception as exc:
                logger.exception("Error re-evaluating backorders for SO %s: %s", so.id, exc)
                error_count += 1

        await db.commit()

    logger.info(
        "re_evaluate_backorders: confirmed=%d errors=%d",
        confirmed_count,
        error_count,
    )
    return {"confirmed_lines": confirmed_count, "errors": error_count}
