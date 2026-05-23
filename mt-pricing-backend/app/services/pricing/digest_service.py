"""Servicio para agregación del digest diario de precios (US-1B-02-07)."""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.pricing import Price

logger = logging.getLogger(__name__)

# Status incluidos en el digest
_DIGEST_STATUSES = ("pending_review", "auto_approved", "approved", "escalated_count")


class DigestService:
    """Agrega métricas diarias de precios para el digest de las 18:00 UAE."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_daily_summary(self, target_date: date) -> dict:
        """Devuelve conteos de prices por estado para la fecha dada.

        Los conteos se basan en `created_at` del día (00:00–23:59 UTC).
        Adicionalmente retorna el conteo de prices con `escalated=True`
        independientemente del status, para visibilidad operativa.

        Returns:
            {
                "date": "YYYY-MM-DD",
                "pending_review": int,
                "auto_approved": int,
                "approved": int,
                "escalated": int,   # prices con escalated=True creados hoy
                "total": int,
            }
        """
        day_start = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        )
        day_end = datetime(
            target_date.year,
            target_date.month,
            target_date.day,
            23,
            59,
            59,
            999999,
            tzinfo=timezone.utc,
        )

        # Counts por status
        stmt_status = (
            select(Price.status, func.count(Price.id).label("cnt"))
            .where(Price.created_at >= day_start)
            .where(Price.created_at <= day_end)
            .group_by(Price.status)
        )
        result_status = await self.session.execute(stmt_status)
        status_counts: dict[str, int] = {row.status: row.cnt for row in result_status}

        # Count escalados del día
        stmt_esc = (
            select(func.count(Price.id))
            .where(Price.created_at >= day_start)
            .where(Price.created_at <= day_end)
            .where(Price.escalated.is_(True))
        )
        result_esc = await self.session.execute(stmt_esc)
        escalated_count: int = result_esc.scalar_one_or_none() or 0

        pending_review = status_counts.get("pending_review", 0)
        auto_approved = status_counts.get("auto_approved", 0)
        approved = status_counts.get("approved", 0)
        total = sum(status_counts.values())

        summary = {
            "date": target_date.isoformat(),
            "pending_review": pending_review,
            "auto_approved": auto_approved,
            "approved": approved,
            "escalated": escalated_count,
            "total": total,
        }
        logger.info(
            "digest_service.daily_summary date=%s pending=%d auto_approved=%d approved=%d escalated=%d total=%d",
            target_date.isoformat(),
            pending_review,
            auto_approved,
            approved,
            escalated_count,
            total,
        )
        return summary


__all__ = ["DigestService"]
