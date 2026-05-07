"""Escalation service — propuestas `pending_review` > 48h (US-1B-02-08).

Marca `prices.escalated=true`, registra audit `price.escalated`, y crea
notificación in-app al delegado del proposed_by/manager (o fallback al
rol `ti_integracion` si no hay delegado configurado).

Idempotente — si una propuesta ya tiene `escalated=true`, NO duplica
notificación ni audit.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pricing import Price
from app.db.models.user import Role, User
from app.repositories.audit import AuditRepository
from app.repositories.notifications import NotificationsRepository

logger = logging.getLogger(__name__)

DEFAULT_ESCALATION_HOURS = 48
FALLBACK_ROLE_CODE = "ti_integracion"
NOTIFICATION_KIND = "price.escalated"
AUDIT_ACTION = "price.escalated"


class EscalationService:
    """Coordina detección + notificación + audit. Sin commit — el caller decide."""

    def __init__(
        self,
        session: AsyncSession,
        *,
        window_hours: int = DEFAULT_ESCALATION_HOURS,
    ) -> None:
        self.session = session
        self.window_hours = window_hours
        self.audit = AuditRepository(session)
        self.notifications = NotificationsRepository(session)

    async def find_overdue_pending_reviews(self) -> list[Price]:
        """Selecciona `pending_review` con `updated_at` o `created_at` > window.

        El criterio usa `updated_at` (refresh por revise) como tiempo desde la
        última transición a `pending_review`, fallback a `created_at`.
        """
        cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=self.window_hours)
        stmt = (
            select(Price)
            .where(Price.status == "pending_review")
            .where(Price.escalated.is_(False))
            .where(Price.updated_at <= cutoff)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars())

    async def _resolve_delegate(self, proposer_id) -> tuple[User | None, str]:
        """Devuelve (delegate_user, reason). Reason ∈ {'delegate', 'fallback', 'none'}."""
        if proposer_id is None:
            return None, "none"
        proposer = await self.session.get(User, proposer_id)
        if proposer is None or proposer.delegate_user_id is None:
            fallback = await self._fetch_fallback_recipient()
            if fallback is None:
                return None, "none"
            return fallback, "fallback"
        delegate = await self.session.get(User, proposer.delegate_user_id)
        if delegate is None or not delegate.is_active:
            fallback = await self._fetch_fallback_recipient()
            if fallback is None:
                return None, "none"
            return fallback, "fallback"
        return delegate, "delegate"

    async def _fetch_fallback_recipient(self) -> User | None:
        stmt = (
            select(User)
            .join(Role, Role.id == User.role_id)
            .where(Role.code == FALLBACK_ROLE_CODE)
            .where(User.is_active.is_(True))
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def escalate(self, price: Price) -> dict:
        """Marca + notifica + audit. Idempotente."""
        if price.escalated:
            return {"price_id": str(price.id), "skipped": True, "reason": "already_escalated"}

        recipient, recipient_reason = await self._resolve_delegate(price.proposed_by)
        now = datetime.now(tz=timezone.utc)
        price.escalated = True
        price.escalated_at = now
        await self.session.flush()

        payload = {
            "price_id": str(price.id),
            "product_sku": price.product_sku,
            "channel_id": str(price.channel_id),
            "scheme_code": price.scheme_code,
            "amount": str(price.amount),
            "status": price.status,
            "escalated_at": now.isoformat(),
            "no_delegate": recipient_reason == "fallback",
        }

        notification_id = None
        if recipient is not None:
            notif = await self.notifications.create(
                recipient_user_id=recipient.id,
                kind=NOTIFICATION_KIND,
                payload=payload,
            )
            notification_id = str(notif.id)
        else:
            logger.warning(
                "escalate_price: no recipient resolved for price %s — emitting audit only",
                price.id,
            )

        await self.audit.record(
            entity_type="price",
            entity_id=str(price.id),
            action=AUDIT_ACTION,
            after={
                **payload,
                "recipient_reason": recipient_reason,
                "recipient_user_id": str(recipient.id) if recipient else None,
                "notification_id": notification_id,
            },
        )

        return {
            "price_id": str(price.id),
            "skipped": False,
            "recipient_reason": recipient_reason,
            "notification_id": notification_id,
        }

    async def run_sweep(self) -> dict:
        """Procesa todas las pendientes overdue. Caller commits al final."""
        overdue = await self.find_overdue_pending_reviews()
        results = []
        for price in overdue:
            results.append(await self.escalate(price))
        escalated = sum(1 for r in results if not r["skipped"])
        return {
            "checked": len(overdue),
            "escalated": escalated,
            "details": results,
            "window_hours": self.window_hours,
        }


__all__ = ["DEFAULT_ESCALATION_HOURS", "EscalationService"]
