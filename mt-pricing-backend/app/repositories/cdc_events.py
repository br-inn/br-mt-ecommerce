"""Repository para `cdc_events` (US-RND-01-11).

Operaciones expuestas:
- ``enqueue(entity_type, entity_id, action, payload)`` — insert programático.
- ``count_by_status()`` — health endpoint.
- ``list_pending(limit)`` — para uso del dispatcher (atajo a select).
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.cdc_event import CDC_EVENT_ACTIONS, CdcEvent


class CdcEventsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def enqueue(
        self,
        *,
        entity_type: str,
        entity_id: str,
        action: str,
        payload: dict[str, Any] | None = None,
    ) -> CdcEvent:
        if action not in CDC_EVENT_ACTIONS:
            raise ValueError(
                f"action='{action}' no soportada. Esperaba {CDC_EVENT_ACTIONS}."
            )
        row = CdcEvent(
            entity_type=entity_type,
            entity_id=entity_id,
            action=action,
            payload_jsonb=payload or {},
            status="pending",
        )
        self.session.add(row)
        await self.session.flush()
        return row

    async def list_pending(self, limit: int = 100) -> Sequence[CdcEvent]:
        stmt = (
            select(CdcEvent)
            .where(CdcEvent.status == "pending")
            .order_by(CdcEvent.id.asc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_by_status(self) -> dict[str, int]:
        stmt = select(CdcEvent.status, func.count()).group_by(CdcEvent.status)
        result = await self.session.execute(stmt)
        return {str(status): int(count) for status, count in result.all()}


__all__ = ["CdcEventsRepository"]
