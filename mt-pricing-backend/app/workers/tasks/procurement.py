"""Tasks de procurement — queue `default`.

Task ``mt.procurement.check_approval_timeouts``:
  Detecta PRs en pending_approval cuyo timeout ha expirado.
  Las escala creando una ApprovalDecision ESCALATE y actualiza el estado
  de vuelta a pending_approval (la responsabilidad pasa al siguiente nivel).
  Se ejecuta cada hora via beat_schedule.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from app.workers.worker import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> Any:
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
    name="mt.procurement.check_approval_timeouts",
    queue="default",
    ignore_result=True,
)
def check_approval_timeouts(self: Any) -> None:
    """Escala PRs en pending_approval con timeout vencido."""
    _run_async(_do_check_timeouts())


async def _do_check_timeouts() -> None:
    from sqlalchemy import select

    from app.db.engine import get_sessionmaker
    from app.db.models.procurement import ApprovalDecision, ApprovalRule, PurchaseRequisition

    async with get_sessionmaker()() as session:
        now = datetime.now(tz=UTC)

        # Cargar PRs en pending_approval
        stmt = select(PurchaseRequisition).where(PurchaseRequisition.status == "pending_approval")
        prs = list((await session.execute(stmt)).scalars().all())

        for pr in prs:
            rule_stmt = (
                select(ApprovalRule)
                .where(
                    ApprovalRule.document_type == "purchase_requisition",
                    ApprovalRule.is_active.is_(True),
                )
                .order_by(ApprovalRule.priority.asc())
                .limit(1)
            )
            rule = (await session.execute(rule_stmt)).scalar_one_or_none()
            if rule is None:
                continue

            timeout_delta = timedelta(hours=rule.timeout_hours)
            if rule.timeout_hours == 0:
                continue

            deadline = pr.updated_at.replace(tzinfo=UTC) + timeout_delta
            if now < deadline:
                continue

            logger.info(
                "PR %s timeout vencido (regla prioridad %s, %sh) — escalando",
                pr.pr_number,
                rule.priority,
                rule.timeout_hours,
            )

            escalation = ApprovalDecision(
                document_id=pr.id,
                document_type="purchase_requisition",
                approver_id=pr.requester_id,
                action="ESCALATE",
                reason=(
                    f"Timeout {rule.timeout_hours}h vencido. "
                    f"Regla prioridad {rule.priority} ({rule.approver_role or 'manual'})."
                ),
            )
            session.add(escalation)
            pr.updated_at = now

        await session.commit()
        logger.info("check_approval_timeouts completado — %d PRs revisadas", len(prs))
