"""Notifications repository — append-only inbox queries (US-1B-02-08)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.notification import Notification


class NotificationsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def create(
        self,
        *,
        recipient_user_id: UUID,
        kind: str,
        payload: dict,
    ) -> Notification:
        notif = Notification(
            recipient_user_id=recipient_user_id,
            kind=kind,
            payload=payload,
        )
        self.session.add(notif)
        await self.session.flush()
        return notif

    async def list_inbox(
        self,
        *,
        recipient_user_id: UUID,
        unseen_only: bool = False,
        limit: int = 50,
    ) -> list[Notification]:
        stmt = (
            select(Notification)
            .where(Notification.recipient_user_id == recipient_user_id)
            .order_by(Notification.created_at.desc())
            .limit(limit)
        )
        if unseen_only:
            stmt = stmt.where(Notification.seen_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def mark_seen(self, *, notification_id: UUID, recipient_user_id: UUID) -> int:
        stmt = (
            update(Notification)
            .where(Notification.id == notification_id)
            .where(Notification.recipient_user_id == recipient_user_id)
            .where(Notification.seen_at.is_(None))
            .values(seen_at=datetime.now(tz=UTC))
        )
        result = await self.session.execute(stmt)
        return result.rowcount or 0


__all__ = ["NotificationsRepository"]
