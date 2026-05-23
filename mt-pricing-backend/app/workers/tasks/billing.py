"""Tasks de Billing — EP-ERP-05.

Task ``mt.billing.run_dunning_check`` (US-ERP-05-03):
  Para cada invoice posted con due_date < today:
  - Calcula días de mora
  - Asigna dunning_level según tabla dunning_levels
  - Si nivel subió: inserta en dunning_history y crea notification
  Cron: 0 8 * * * (diario a las 8am)

Task ``mt.billing.check_unposted_deliveries`` (US-ERP-05-06):
  Detecta outbound_deliveries.shipped_at < now() - 24h sin invoice asociada
  → crea notification tipo 'billing_alert_24h'
  Cron: 0 */4 * * * (cada 4 horas)

Task ``mt.billing.mark_broken_promises`` (US-ERP-05-05):
  Marca como 'broken' las promesas con promised_date < today y status='active'.
  Cron: 0 8 * * * (diario)
"""

from __future__ import annotations

import asyncio
import logging
from datetime import date, datetime, timedelta, timezone
from typing import Any

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


# ---------------------------------------------------------------------------
# US-ERP-05-03 — Dunning check diario
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.billing.run_dunning_check",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="default",
)
def run_dunning_check(self: Any) -> dict[str, Any]:  # noqa: ANN401
    """Evalúa invoices en mora y registra historial de dunning."""
    return _run_async(_run_dunning_check_async())


async def _run_dunning_check_async() -> dict[str, Any]:
    from sqlalchemy import select

    from app.db import get_db_session
    from app.db.models.billing import DunningHistory, DunningLevel, Invoice
    from app.db.models.notification import Notification

    processed = 0
    escalated = 0
    errors = 0
    today = date.today()

    async with get_db_session() as session:
        # Load active dunning levels
        dl_result = await session.execute(
            select(DunningLevel).where(DunningLevel.is_active == True).order_by(DunningLevel.level)  # noqa: E712
        )
        levels = list(dl_result.scalars().all())
        if not levels:
            return {
                "processed": 0,
                "escalated": 0,
                "errors": 0,
                "note": "no dunning levels configured",
            }

        # Overdue invoices
        q = select(Invoice).where(
            Invoice.status == "posted",
            Invoice.due_date < today,
        )
        result = await session.execute(q)
        invoices = list(result.scalars().all())

        for inv in invoices:
            try:
                if inv.due_date is None:
                    continue
                days_overdue = (today - inv.due_date).days
                current_level = 0
                for dl in reversed(levels):
                    if days_overdue >= dl.days_overdue:
                        current_level = dl.level
                        break

                if current_level == 0:
                    continue

                # Check last dunning history for this invoice
                last_result = await session.execute(
                    select(DunningHistory)
                    .where(DunningHistory.invoice_id == inv.id)
                    .order_by(DunningHistory.sent_at.desc())
                    .limit(1)
                )
                last = last_result.scalar_one_or_none()
                last_level = last.dunning_level if last else 0

                if current_level > last_level:
                    # Escalate — insert dunning history
                    history = DunningHistory(
                        invoice_id=inv.id,
                        customer_id=inv.customer_id,
                        dunning_level=current_level,
                        notes=f"Auto-dunning: {days_overdue} days overdue",
                    )
                    session.add(history)

                    # Create notification
                    notification = Notification(
                        event_type="dunning_alert",
                        payload={
                            "invoice_id": str(inv.id),
                            "invoice_number": inv.invoice_number,
                            "customer_id": inv.customer_id,
                            "dunning_level": current_level,
                            "days_overdue": days_overdue,
                            "amount": str(inv.total_amount),
                        },
                    )
                    session.add(notification)
                    escalated += 1

                processed += 1
            except Exception as exc:
                logger.error("dunning check error for invoice %s: %s", inv.id, exc)
                errors += 1

        await session.commit()

    return {"processed": processed, "escalated": escalated, "errors": errors}


# ---------------------------------------------------------------------------
# US-ERP-05-06 — Check unposted deliveries (billing alert 24h)
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.billing.check_unposted_deliveries",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="default",
)
def check_unposted_deliveries(self: Any) -> dict[str, Any]:  # noqa: ANN401
    """Detecta deliveries sin invoice > 24h y crea alertas."""
    return _run_async(_check_unposted_deliveries_async())


async def _check_unposted_deliveries_async() -> dict[str, Any]:
    from sqlalchemy import select, text

    from app.db import get_db_session
    from app.db.models.notification import Notification
    from app.db.models.sales import OutboundDelivery

    alerted = 0
    errors = 0
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)

    async with get_db_session() as session:
        # Deliveries shipped > 24h ago without any associated invoice
        try:
            result = await session.execute(
                text(
                    """
                    SELECT d.id, d.delivery_number, d.so_id, d.shipped_at
                    FROM outbound_deliveries d
                    WHERE d.shipped_at < :cutoff
                    AND d.status = 'shipped'
                    AND NOT EXISTS (
                        SELECT 1 FROM invoices i WHERE i.delivery_id = d.id
                    )
                    """
                ),
                {"cutoff": cutoff},
            )
            rows = result.fetchall()
        except Exception as exc:
            logger.error("check_unposted_deliveries query error: %s", exc)
            return {"alerted": 0, "errors": 1}

        for row in rows:
            try:
                notification = Notification(
                    event_type="billing_alert_24h",
                    payload={
                        "delivery_id": str(row.id),
                        "delivery_number": row.delivery_number,
                        "so_id": str(row.so_id) if row.so_id else None,
                        "shipped_at": row.shipped_at.isoformat() if row.shipped_at else None,
                        "hours_since_shipment": round(
                            (datetime.now(timezone.utc) - row.shipped_at).total_seconds() / 3600, 1
                        )
                        if row.shipped_at
                        else None,
                    },
                )
                session.add(notification)
                alerted += 1
            except Exception as exc:
                logger.error("billing_alert_24h notification error: %s", exc)
                errors += 1

        if alerted > 0:
            await session.commit()

    return {"alerted": alerted, "errors": errors}


# ---------------------------------------------------------------------------
# US-ERP-05-05 — Mark broken payment promises
# ---------------------------------------------------------------------------


@celery_app.task(
    name="mt.billing.mark_broken_promises",
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    queue="default",
)
def mark_broken_promises(self: Any) -> dict[str, Any]:  # noqa: ANN401
    """Marca promesas vencidas como broken."""
    return _run_async(_mark_broken_promises_async())


async def _mark_broken_promises_async() -> dict[str, Any]:
    from sqlalchemy import update

    from app.db import get_db_session
    from app.db.models.billing import PaymentPromise

    today = date.today()
    marked = 0

    async with get_db_session() as session:
        try:
            result = await session.execute(
                update(PaymentPromise)
                .where(
                    PaymentPromise.promised_date < today,
                    PaymentPromise.status == "active",
                )
                .values(status="broken")
                .returning(PaymentPromise.id)
            )
            marked = len(result.fetchall())
            await session.commit()
        except Exception as exc:
            logger.error("mark_broken_promises error: %s", exc)
            return {"marked": 0, "error": str(exc)}

    return {"marked": marked}
