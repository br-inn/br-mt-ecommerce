"""ERP Sync Events admin routes — US-INV-01-07.

Endpoints:
- ``GET  /admin/erp-eventos``            — lista con filtro status + cursor pagination.
- ``PATCH /admin/erp-eventos/{id}/retry`` — resetea status='pending' y re-encola.

Requieren rol ``admin``.
"""

from __future__ import annotations

import logging
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_role
from app.db.models.inventory import ERPSyncEvent
from app.db.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/admin/erp-eventos", tags=["ERP Eventos Admin"])

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

_VALID_STATUSES = {"pending", "delivered", "failed", "skipped"}


class ERPSyncEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    event_type: str
    entity_id: str | None
    adapter: str
    status: str
    attempts: int
    last_error: str | None
    external_ref: str | None
    delivered_at: str | None
    created_at: str | None
    updated_at: str | None

    @classmethod
    def from_orm_event(cls, ev: ERPSyncEvent) -> "ERPSyncEventOut":
        return cls(
            id=ev.id,
            event_type=ev.event_type,
            entity_id=ev.entity_id,
            adapter=ev.adapter,
            status=ev.status,
            attempts=ev.attempts,
            last_error=ev.last_error,
            external_ref=ev.external_ref,
            delivered_at=ev.delivered_at.isoformat() if ev.delivered_at else None,
            created_at=ev.created_at.isoformat() if ev.created_at else None,
            updated_at=ev.updated_at.isoformat() if ev.updated_at else None,
        )


class ERPSyncEventsPage(BaseModel):
    items: list[ERPSyncEventOut]
    next_cursor: str | None


# ---------------------------------------------------------------------------
# GET /admin/erp-eventos
# ---------------------------------------------------------------------------


@router.get(
    "",
    response_model=ERPSyncEventsPage,
    summary="Lista de ERPSyncEvents con filtro y cursor pagination (admin only)",
)
async def list_erp_eventos(
    current_user: Annotated[User, Depends(require_role("admin"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
    status: str | None = Query(
        default=None, description="Filtrar por status: pending, delivered, failed, skipped"
    ),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(
        default=None, description="Cursor opaco — valor del campo created_at de la última fila"
    ),
) -> ERPSyncEventsPage:
    """Lista ERPSyncEvent con filtro opcional por ``status`` y cursor pagination.

    Cursor basado en ``id`` (UUID lexicográfico) para paginación estable.
    """
    if status is not None and status not in _VALID_STATUSES:
        raise HTTPException(
            status_code=422,
            detail=f"status inválido: '{status}'. Válidos: {sorted(_VALID_STATUSES)}",
        )

    stmt = select(ERPSyncEvent).order_by(ERPSyncEvent.created_at.desc(), ERPSyncEvent.id.desc())  # type: ignore[attr-defined]

    if status is not None:
        stmt = stmt.where(ERPSyncEvent.status == status)

    if cursor is not None:
        # Cursor = str(UUID) de la última fila vista
        try:
            cursor_id = UUID(cursor)
        except ValueError:
            raise HTTPException(status_code=422, detail="cursor inválido")
        # Para paginación simple con UUID, usamos id < cursor_id (ordenado DESC)
        stmt = stmt.where(ERPSyncEvent.id < cursor_id)  # type: ignore[operator]

    stmt = stmt.limit(limit + 1)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    next_cursor = str(rows[-1].id) if has_more and rows else None

    return ERPSyncEventsPage(
        items=[ERPSyncEventOut.from_orm_event(r) for r in rows],
        next_cursor=next_cursor,
    )


# ---------------------------------------------------------------------------
# PATCH /admin/erp-eventos/{event_id}/retry
# ---------------------------------------------------------------------------


@router.patch(
    "/{event_id}/retry",
    response_model=ERPSyncEventOut,
    summary="Resetea y re-encola un ERPSyncEvent fallido (admin only)",
)
async def retry_erp_evento(
    event_id: UUID,
    current_user: Annotated[User, Depends(require_role("admin"))],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ERPSyncEventOut:
    """Busca el evento, verifica ``status='failed'``, resetea a ``pending``
    y re-encola ``push_erp_event``.
    """
    event = await session.get(ERPSyncEvent, event_id)
    if event is None:
        raise HTTPException(status_code=404, detail="ERPSyncEvent no encontrado")

    if event.status != "failed":
        raise HTTPException(
            status_code=409,
            detail=f"Solo se puede reintentar eventos en estado 'failed'. Estado actual: '{event.status}'",
        )

    event.status = "pending"
    event.attempts = 0
    event.last_error = None
    await session.commit()
    await session.refresh(event)

    # Encolar task fuera de transacción (ya commiteado)
    try:
        from app.workers.tasks.erp_sync import push_erp_event

        push_erp_event.delay(str(event_id))
        logger.info("retry_erp_evento: re-enqueued event_id=%s", event_id)
    except Exception:  # noqa: BLE001
        logger.warning(
            "retry_erp_evento: could not enqueue push_erp_event for event_id=%s",
            event_id,
            exc_info=True,
        )

    return ERPSyncEventOut.from_orm_event(event)
