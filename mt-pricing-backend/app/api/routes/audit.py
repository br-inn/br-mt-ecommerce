"""Audit events read-only endpoint.

US-1A-07-01 (Sprint 1.5): expone una timeline filtrable y paginada de
`audit_events`. Es el endpoint que consumen los tabs "Auditoría" en
producto, usuario y job.

Convenciones:
- Cursor opaco base64url-JSON `{"at": "<iso>", "id": <bigint>}` — keyset
  pagination sobre `(event_at desc, id desc)`.
- Permission gating: `audit:read` (cubre productos/usuarios/jobs/roles).
- Solo lectura: la persistencia ocurre vía `AuditRepository.record` desde los
  servicios de dominio (mutations).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.api.pagination import decode_cursor, encode_cursor
from app.db.models.audit import AuditEvent
from app.db.models.user import User
from app.repositories.audit import PRICE_TIMELINE_MAX_ROWS, AuditFilters, AuditRepository
from app.schemas.audit import AuditActorRef, AuditEventResponse
from app.schemas.common import Cursor, Pagination

router = APIRouter(prefix="/audit", tags=["Audit"])


def _build_audit_event_response(evt: AuditEvent, actor_user: User | None) -> AuditEventResponse:
    """Helper compartido para construir AuditEventResponse desde (evt, actor_user)."""
    actor_ref: AuditActorRef | None = None
    if evt.actor_id is not None:
        actor_ref = AuditActorRef(
            id=evt.actor_id,
            email=(actor_user.email if actor_user is not None else evt.actor_email),
            full_name=(actor_user.full_name if actor_user is not None else None),
        )
    elif evt.actor_email is not None:
        actor_ref = AuditActorRef(
            id=None,
            email=evt.actor_email,
            full_name=None,
        )
    return AuditEventResponse(
        id=str(evt.id),
        event_at=evt.event_at,
        actor=actor_ref,
        entity_type=evt.entity_type,
        entity_id=evt.entity_id,
        action=evt.action,
        before=evt.before,
        after=evt.after,
        payload_diff=evt.payload_diff or {},
        reason=evt.reason,
        request_id=evt.request_id,
        current_hash=evt.current_hash,
        prev_hash=evt.prev_hash,
    )


def _decode_audit_cursor(cursor: str | None) -> tuple[datetime, int] | None:
    if cursor is None:
        return None
    payload = decode_cursor(cursor)
    at_raw = payload.get("at")
    id_raw = payload.get("id")
    if not isinstance(at_raw, str) or not isinstance(id_raw, int):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://mtme-api/errors/invalid-cursor",
                "title": "Invalid cursor",
                "status": 400,
                "code": "invalid_cursor",
                "detail": "Cursor de audit debe contener 'at' (ISO datetime) e 'id' (int).",
            },
        )
    try:
        at = datetime.fromisoformat(at_raw)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "type": "https://mtme-api/errors/invalid-cursor",
                "title": "Invalid cursor",
                "status": 400,
                "code": "invalid_cursor",
                "detail": "Cursor 'at' no es ISO datetime válido.",
            },
        ) from exc
    return at, id_raw


def _encode_audit_cursor(value: tuple[datetime, int] | None) -> str | None:
    if value is None:
        return None
    at, id_ = value
    return encode_cursor({"at": at.isoformat(), "id": id_})


@router.get(
    "/events",
    response_model=Pagination[AuditEventResponse],
    summary="Listar audit events con filtros + cursor pagination",
)
async def list_audit_events(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permissions("audit:read"))],
    entity_type: Annotated[str | None, Query(description="Tipo de entidad (product/user/job/role).")] = None,
    entity_id: Annotated[str | None, Query(description="ID o SKU de la entidad.")] = None,
    actor_id: Annotated[UUID | None, Query(description="Filtrar por usuario que originó el evento.")] = None,
    action: Annotated[str | None, Query(description="Acción concreta (create/update/delete/...).")] = None,
    since: Annotated[datetime | None, Query(description="Lower bound (ISO).")] = None,
    until: Annotated[datetime | None, Query(description="Upper bound (ISO).")] = None,
    cursor: Annotated[str | None, Query(description="Cursor opaco devuelto en respuesta previa.")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> Pagination[AuditEventResponse]:
    repo = AuditRepository(session)
    decoded_cursor = _decode_audit_cursor(cursor)
    filters = AuditFilters(
        entity_type=entity_type,
        entity_id=entity_id,
        actor_id=actor_id,
        action=action,
        since=since,
        until=until,
    )
    rows, next_cursor = await repo.list_paginated(
        filters, cursor=decoded_cursor, limit=limit
    )

    items: list[AuditEventResponse] = [
        _build_audit_event_response(evt, actor_user) for evt, actor_user in rows
    ]

    return Pagination[AuditEventResponse](
        items=items,
        cursor=Cursor(next=_encode_audit_cursor(next_cursor)),
        page_size=limit,
    )


@router.get(
    "/prices/{price_id}/timeline",
    response_model=list[AuditEventResponse],
    summary="Timeline de audit events de un precio (ASC)",
)
async def get_price_timeline(
    price_id: UUID,
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permissions("audit:read"))],
) -> list[AuditEventResponse]:
    """Devuelve todos los audit events de `entity_type='price'` para el precio dado,
    ordenados cronológicamente ASC. Máx `PRICE_TIMELINE_MAX_ROWS` eventos — sin paginación.
    """
    repo = AuditRepository(session)
    rows = await repo.list_price_timeline(price_id, limit=PRICE_TIMELINE_MAX_ROWS)
    return [_build_audit_event_response(evt, actor_user) for evt, actor_user in rows]
