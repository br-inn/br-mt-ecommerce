"""GET /api/v1/audit-events — query multi-entidad para tab Auditoría (US-1A-07-03).

Endpoint nuevo (NO reemplaza `/api/v1/audit/events`). Soporta:

- ``entity_type`` (CSV): `products,costs,prices,product_translations`.
- ``entity_id`` (CSV): permite filtrar varios ids al mismo tiempo (e.g. el
  mismo SKU referenciado por products + product_translations + costs).
- ``related_sku``: shortcut para "tráeme todo el timeline de este SKU".
- ``from`` / ``to``: rango temporal ISO-8601.
- ``actor`` (UUID o email partial): filtra por usuario.
- ``action`` (CSV): filtra acciones (`price.proposed`, `price.approved`...).
- ``cursor`` opaco / ``limit`` 1-200.

Permission: ``audit:read`` (igual que el endpoint legacy — gerente y TI).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.api.pagination import decode_cursor, encode_cursor
from app.db.models.user import User
from app.schemas.audit_query import (
    AuditQueryActor,
    AuditQueryCursor,
    AuditQueryItem,
    AuditQueryResponse,
)
from app.services.audit.audit_query_service import (
    AuditQueryFilters,
    AuditQueryService,
)

router = APIRouter(prefix="/audit-events", tags=["Audit"])


def _split_csv(value: str | None) -> tuple[str, ...] | None:
    if value is None:
        return None
    parts = tuple(p.strip() for p in value.split(",") if p.strip())
    return parts or None


def _decode_cursor(cursor: str | None) -> tuple[datetime, int] | None:
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
                "detail": "Cursor debe contener 'at' (ISO datetime) e 'id' (int).",
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


def _encode_cursor(value: tuple[datetime, int] | None) -> str | None:
    if value is None:
        return None
    at, id_ = value
    return encode_cursor({"at": at.isoformat(), "id": id_})


@router.get(
    "",
    response_model=AuditQueryResponse,
    summary="Audit timeline multi-entidad (tab Auditoría SKU detail)",
    description=(
        "Query unificada del log de auditoría con filtros multi-entidad "
        "(entity_type, entity_id, related_sku, actor, action, rango "
        "temporal). Cursor-based pagination. Permission `audit:read`."
    ),
    operation_id="auditQueryList",
)
async def list_audit_events_multi(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permissions("audit:read"))],
    entity_type: Annotated[
        str | None,
        Query(description="CSV de entity_types (e.g. 'products,costs,prices')."),
    ] = None,
    entity_id: Annotated[
        str | None, Query(description="CSV de entity_ids (e.g. 'MT-V-038').")
    ] = None,
    related_sku: Annotated[
        str | None,
        Query(description="Shortcut: timeline unificado para este SKU."),
    ] = None,
    actor: Annotated[
        str | None,
        Query(description="UUID o email partial del actor."),
    ] = None,
    action: Annotated[
        str | None, Query(description="CSV de acciones (e.g. 'price.proposed').")
    ] = None,
    from_: Annotated[
        datetime | None, Query(alias="from", description="Lower bound ISO.")
    ] = None,
    to: Annotated[
        datetime | None, Query(description="Upper bound ISO.")
    ] = None,
    cursor: Annotated[
        str | None, Query(description="Cursor opaco devuelto en respuesta previa.")
    ] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> AuditQueryResponse:
    actor_id: UUID | None = None
    actor_email: str | None = None
    if actor is not None:
        try:
            actor_id = UUID(actor)
        except ValueError:
            actor_email = actor

    filters = AuditQueryFilters(
        entity_types=_split_csv(entity_type),
        entity_ids=_split_csv(entity_id),
        related_sku=related_sku,
        actor_id=actor_id,
        actor_email=actor_email,
        actions=_split_csv(action),
        since=from_,
        until=to,
    )

    decoded_cursor = _decode_cursor(cursor)
    service = AuditQueryService(session)
    result = await service.query(filters, cursor=decoded_cursor, limit=limit)

    items: list[AuditQueryItem] = []
    for row in result.items:
        actor_obj: AuditQueryActor | None = None
        if row.actor_id is not None or row.actor_email is not None:
            actor_obj = AuditQueryActor(
                id=row.actor_id,
                email=row.actor_email,
                full_name=row.actor_full_name,
            )
        items.append(
            AuditQueryItem(
                id=row.id,
                event_at=row.event_at,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                action=row.action,
                actor=actor_obj,
                before=row.before,
                after=row.after,
                payload_diff=row.payload_diff,
                reason=row.reason,
            )
        )

    return AuditQueryResponse(
        items=items,
        cursor=AuditQueryCursor(next=_encode_cursor(result.next_cursor)),
        page_size=limit,
    )
