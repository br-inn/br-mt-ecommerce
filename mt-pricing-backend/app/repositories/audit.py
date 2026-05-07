"""AuditRepository — write-mostly. El hash chain lo calcula el trigger SQL.

El servicio que persiste audit events sólo provee `entity_type`, `entity_id`,
`action`, `actor_id`, `before/after/payload_diff`, `reason`. El trigger
`audit_events_hash_chain_trigger` calcula `prev_hash` + `current_hash`
dentro de la transacción.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select

from app.db.models.audit import AuditEvent
from app.db.models.user import User
from app.repositories.base import BaseRepository


@dataclass(frozen=True)
class AuditFilters:
    """Filtro normalizado para listing paginado de audit events."""

    entity_type: str | None = None
    entity_id: str | None = None
    actor_id: UUID | None = None
    action: str | None = None
    since: datetime | None = None
    until: datetime | None = None


def _jsonb_safe(value: Any) -> Any:
    """Convierte recursivamente Decimal/datetime/date/UUID a str para JSONB.

    asyncpg + SQLAlchemy serializan dict→JSONB con json.dumps; Decimal/UUID/etc.
    no son serializables nativamente y rompen toda la transacción. Mejor
    convertirlos a str defensivamente.
    """
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (Decimal, datetime, date, UUID)):
        return str(value)
    if isinstance(value, dict):
        return {k: _jsonb_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonb_safe(v) for v in value]
    return value


class AuditRepository(BaseRepository[AuditEvent]):
    model = AuditEvent
    pk_field = "id"
    soft_delete_field = None

    async def record(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        actor_id: UUID | None = None,
        actor_email: str | None = None,
        actor_role: str | None = None,
        before: dict | None = None,
        after: dict | None = None,
        payload_diff: dict | None = None,
        reason: str | None = None,
        request_id: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> AuditEvent:
        # Sanitización defensiva — Decimal/datetime/UUID nunca son JSON-serializables
        # para asyncpg JSONB. Aplicamos antes de persistir cualquier evento.
        evt = AuditEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            actor_id=actor_id,
            actor_email=actor_email,
            actor_role=actor_role,
            before=_jsonb_safe(before),
            after=_jsonb_safe(after),
            payload_diff=_jsonb_safe(payload_diff) or {},
            reason=reason,
            request_id=request_id,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.session.add(evt)
        await self.session.flush()
        return evt

    async def list_for_entity(
        self,
        entity_type: str,
        entity_id: str,
        *,
        since: datetime | None = None,
        limit: int = 100,
    ) -> Sequence[AuditEvent]:
        stmt = select(AuditEvent).where(
            AuditEvent.entity_type == entity_type,
            AuditEvent.entity_id == entity_id,
        )
        if since:
            stmt = stmt.where(AuditEvent.event_at >= since)
        stmt = stmt.order_by(AuditEvent.event_at.desc()).limit(limit)
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_by_actor(
        self, actor_id: UUID, *, limit: int = 100
    ) -> Sequence[AuditEvent]:
        stmt = (
            select(AuditEvent)
            .where(AuditEvent.actor_id == actor_id)
            .order_by(AuditEvent.event_at.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return result.scalars().all()

    async def list_paginated(
        self,
        filters: AuditFilters,
        *,
        cursor: tuple[datetime, int] | None = None,
        limit: int = 50,
    ) -> tuple[list[tuple[AuditEvent, User | None]], tuple[datetime, int] | None]:
        """Paginated keyset listing con join opcional a users (resuelve actor email/name).

        Cursor es la tupla `(event_at, id)` del último item; el siguiente page
        empieza con eventos estrictamente anteriores (orden DESC por event_at, id).
        """
        stmt = select(AuditEvent, User).join(
            User, User.id == AuditEvent.actor_id, isouter=True
        )

        conditions = []
        if filters.entity_type is not None:
            conditions.append(AuditEvent.entity_type == filters.entity_type)
        if filters.entity_id is not None:
            conditions.append(AuditEvent.entity_id == filters.entity_id)
        if filters.actor_id is not None:
            conditions.append(AuditEvent.actor_id == filters.actor_id)
        if filters.action is not None:
            conditions.append(AuditEvent.action == filters.action)
        if filters.since is not None:
            conditions.append(AuditEvent.event_at >= filters.since)
        if filters.until is not None:
            conditions.append(AuditEvent.event_at <= filters.until)

        if cursor is not None:
            cursor_at, cursor_id = cursor
            # keyset: registros estrictamente "anteriores" en orden (event_at desc, id desc)
            conditions.append(
                or_(
                    AuditEvent.event_at < cursor_at,
                    and_(
                        AuditEvent.event_at == cursor_at,
                        AuditEvent.id < cursor_id,
                    ),
                )
            )

        if conditions:
            stmt = stmt.where(*conditions)

        stmt = stmt.order_by(
            AuditEvent.event_at.desc(),
            AuditEvent.id.desc(),
        ).limit(limit + 1)

        result = await self.session.execute(stmt)
        rows: list[tuple[AuditEvent, User | None]] = [
            (row[0], row[1]) for row in result.all()
        ]
        next_cursor: tuple[datetime, int] | None = None
        if len(rows) > limit:
            last = rows[limit - 1][0]
            next_cursor = (last.event_at, last.id)
            rows = rows[:limit]
        return rows, next_cursor
