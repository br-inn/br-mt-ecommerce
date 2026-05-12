"""Audit events read-only endpoint.

US-1A-07-01 (Sprint 1.5): expone una timeline filtrable y paginada de
`audit_events`. Es el endpoint que consumen los tabs "Auditoría" en
producto, usuario y job.

ADR-076 / R-005: agrega GET /audit/verify para verificación ad-hoc del
hash chain (VAT UAE 2026).

Convenciones:
- Cursor opaco base64url-JSON `{"at": "<iso>", "id": <bigint>}` — keyset
  pagination sobre `(event_at desc, id desc)`.
- Permission gating: `audit:read` (cubre productos/usuarios/jobs/roles).
- Solo lectura: la persistencia ocurre vía `AuditRepository.record` desde los
  servicios de dominio (mutations).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.api.pagination import decode_cursor, encode_cursor
from app.db.models.audit import AuditEvent
from app.db.models.user import User
from app.repositories.audit import PRICE_TIMELINE_MAX_ROWS, AuditFilters, AuditRepository
from app.schemas.audit import AuditActorRef, AuditEventResponse
from app.schemas.common import Cursor, Pagination

_VERIFY_MAX_DAYS = 7  # máximo rango permitido en GET /audit/verify

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


# ---------------------------------------------------------------------------
# ADR-076 / R-005 — Verificación ad-hoc del hash chain
# ---------------------------------------------------------------------------

class AuditVerifyResponse(BaseModel):
    verified: bool
    range: dict[str, str]
    rows_checked: int
    tampered_ids: list[int]
    checked_at: str


def _compute_row_hash_sync(
    row_id: int,
    event_at: datetime,
    actor_id: str | None,
    entity_type: str,
    entity_id: str,
    action: str,
    payload_diff: Any,
    prev_hash: str,
) -> str:
    """Recomputa el hash de una fila — misma lógica que audit_integrity.py."""
    import hashlib
    import json

    if isinstance(payload_diff, dict):
        payload_str = json.dumps(payload_diff, separators=(",", ":"), sort_keys=True)
    elif payload_diff is None:
        payload_str = "{}"
    else:
        payload_str = str(payload_diff)

    event_at_str = event_at.isoformat() if event_at is not None else ""

    row_data = (
        (str(row_id) if row_id is not None else "")
        + event_at_str
        + (str(actor_id) if actor_id is not None else "")
        + (entity_type or "")
        + (entity_id or "")
        + (action or "")
        + payload_str
        + (prev_hash or "")
    )
    return hashlib.sha256(row_data.encode()).hexdigest()


@router.get(
    "/verify",
    response_model=AuditVerifyResponse,
    summary="Verifica integridad del hash chain para un rango de fechas (ADR-076)",
    responses={
        200: {"description": "Hash chain íntegro"},
        409: {"description": "Tamper detectado — filas alteradas"},
        422: {"description": "Rango inválido o supera 7 días"},
    },
)
async def verify_audit_chain(
    session: Annotated[AsyncSession, Depends(get_db_session)],
    _: Annotated[User, Depends(require_permissions("audit:read"))],
    from_dt: Annotated[
        datetime,
        Query(alias="from", description="Inicio del rango (ISO8601, UTC recomendado)."),
    ],
    to_dt: Annotated[
        datetime,
        Query(alias="to", description="Fin del rango (ISO8601, UTC recomendado)."),
    ],
) -> AuditVerifyResponse:
    """Verifica el hash chain de ``audit_events`` en el rango [from, to).

    - Rango máximo: 7 días. Rangos mayores retornan HTTP 422.
    - Si se detectan filas alteradas retorna HTTP 409 con los IDs afectados.
    - No genera firma (solo verificación) — para firma diaria ver el job nocturno.
    """
    # Validar rango máximo
    if (to_dt - from_dt) > timedelta(days=_VERIFY_MAX_DAYS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "type": "https://mtme-api/errors/range-too-large",
                "title": "Range too large",
                "status": 422,
                "code": "range_too_large",
                "detail": f"El rango máximo permitido es {_VERIFY_MAX_DAYS} días.",
            },
        )

    if from_dt >= to_dt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "type": "https://mtme-api/errors/invalid-range",
                "title": "Invalid range",
                "status": 422,
                "code": "invalid_range",
                "detail": "'from' debe ser anterior a 'to'.",
            },
        )

    # Ejecutar verificación en thread pool para no bloquear el event loop
    # (la query puede ser costosa y es síncrona por naturaleza del hash chain)
    loop = asyncio.get_event_loop()

    async def _run_verify() -> dict[str, Any]:
        rows_result = await session.execute(
            text(
                """
                SELECT id, event_at, actor_id, entity_type, entity_id,
                       action, payload_diff, prev_hash, current_hash
                FROM audit_events
                WHERE event_at >= :start
                  AND event_at < :end
                ORDER BY id ASC
                """
            ),
            {"start": from_dt, "end": to_dt},
        )
        rows = rows_result.fetchall()

        tampered_ids: list[int] = []
        running_hash = ""

        for row in rows:
            expected = _compute_row_hash_sync(
                row_id=row.id,
                event_at=row.event_at,
                actor_id=str(row.actor_id) if row.actor_id is not None else None,
                entity_type=row.entity_type,
                entity_id=row.entity_id,
                action=row.action,
                payload_diff=row.payload_diff,
                prev_hash=running_hash,
            )
            if expected != row.current_hash:
                tampered_ids.append(row.id)
            running_hash = row.current_hash or running_hash

        return {
            "verified": len(tampered_ids) == 0,
            "rows_checked": len(rows),
            "tampered_ids": tampered_ids,
        }

    result = await _run_verify()

    checked_at = datetime.now(tz=UTC).isoformat()
    resp = AuditVerifyResponse(
        verified=result["verified"],
        range={"from": from_dt.isoformat(), "to": to_dt.isoformat()},
        rows_checked=result["rows_checked"],
        tampered_ids=result["tampered_ids"],
        checked_at=checked_at,
    )

    if not result["verified"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "type": "https://mtme-api/errors/audit-tamper-detected",
                "title": "Audit chain tamper detected",
                "status": 409,
                "code": "audit_tamper_detected",
                "detail": "Se detectaron filas alteradas en el hash chain.",
                "tampered_ids": result["tampered_ids"],
                "rows_checked": result["rows_checked"],
                "range": {"from": from_dt.isoformat(), "to": to_dt.isoformat()},
                "checked_at": checked_at,
            },
        )

    return resp
