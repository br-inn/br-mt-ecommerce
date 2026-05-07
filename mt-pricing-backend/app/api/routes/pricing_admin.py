"""Pricing admin API — bulk-recalc trigger + last-run inspector (US-1B-01-07).

Endpoints expuestos (router montable, no se incluye automáticamente — patch
documentado al final):

- ``POST /api/v1/pricing/admin/bulk-recalc/trigger``
    Manual override: encola ``mt.pricing.bulk_recalc`` con
    ``source='manual_admin'``. RBAC ``prices:propose`` (TI/admin).
- ``GET  /api/v1/pricing/admin/bulk-recalc/last-run``
    Devuelve metadata + summary del último ``audit_events.action='nightly_recalc_batch'``.
    RBAC ``audit:read``.

Nota: este router NO se registra automáticamente en
``app/api/routes/__init__.py`` (constraint del Sprint 5 — sólo archivos
nuevos). Se reporta el parche al final.
"""

from __future__ import annotations

import logging
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.audit import AuditEvent
from app.db.models.user import User
from app.schemas.common import ProblemDetails

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/pricing/admin", tags=["pricing-admin"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------
class BulkRecalcTriggerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=2048)
    source: str = Field(default="manual_admin", max_length=32)


class BulkRecalcTriggerResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    task_id: str
    source: str
    status: str = "queued"


class BulkRecalcLastRunResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    found: bool
    event_at: str | None = None
    actor_email: str | None = None
    summary: dict[str, Any] | None = None
    source: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/bulk-recalc/trigger",
    response_model=BulkRecalcTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Trigger manual del bulk-recalc nocturno (override admin)",
    description=(
        "Encola la task Celery ``mt.pricing.bulk_recalc`` fuera de la "
        "ventana horaria normal (cron 02:00). Útil tras un cambio FX masivo "
        "o un cost adjustment crítico. La task aplica el mismo mutex que el "
        "beat nocturno y skipea si hay un manual recalc activo."
    ),
    operation_id="pricingAdminTriggerBulkRecalc",
    responses={
        503: {"model": ProblemDetails, "description": "Worker pricing no disponible"},
    },
)
async def trigger_bulk_recalc(
    user: Annotated[User, Depends(require_permissions("prices:propose"))],
    payload: BulkRecalcTriggerRequest | None = None,
) -> BulkRecalcTriggerResponse:
    body = payload or BulkRecalcTriggerRequest()
    try:
        from app.workers.tasks.pricing_recalc import bulk_recalc_task
    except Exception as exc:  # pragma: no cover  # noqa: BLE001
        raise HTTPException(
            status_code=503,
            detail={
                "code": "celery_unavailable",
                "title": f"Worker pricing no disponible: {exc!s}",
            },
        ) from exc

    async_result = bulk_recalc_task.delay(body.source)
    task_id = getattr(async_result, "id", "") or ""
    logger.info(
        "pricing_admin.bulk_recalc_triggered",
        extra={
            "actor_id": str(user.id),
            "source": body.source,
            "task_id": task_id,
        },
    )
    return BulkRecalcTriggerResponse(
        task_id=task_id, source=body.source, status="queued"
    )


@router.get(
    "/bulk-recalc/last-run",
    response_model=BulkRecalcLastRunResponse,
    summary="Devuelve metadata + summary del último bulk-recalc nocturno",
    description=(
        "Lee el audit_event más reciente con "
        "``action='nightly_recalc_batch'``. Si no hay ninguno (e.g. primer "
        "deploy, antes del primer cron), devuelve ``found=false``."
    ),
    operation_id="pricingAdminGetBulkRecalcLastRun",
)
async def get_bulk_recalc_last_run(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _user: Annotated[User, Depends(require_permissions("audit:read"))],
) -> BulkRecalcLastRunResponse:
    stmt = (
        select(AuditEvent)
        .where(AuditEvent.action == "nightly_recalc_batch")
        .order_by(desc(AuditEvent.event_at))
        .limit(1)
    )
    last = (await session.execute(stmt)).scalar_one_or_none()
    if last is None:
        return BulkRecalcLastRunResponse(found=False)

    after = getattr(last, "after", None)
    summary = after if isinstance(after, dict) else None
    payload_diff = getattr(last, "payload_diff", None)
    source: str | None = None
    if isinstance(payload_diff, dict):
        raw = payload_diff.get("source")
        if isinstance(raw, str):
            source = raw

    return BulkRecalcLastRunResponse(
        found=True,
        event_at=last.event_at.isoformat() if last.event_at else None,
        actor_email=getattr(last, "actor_email", None),
        summary=summary,
        source=source,
    )


__all__ = ["router"]
