"""Read-only assembly for F4 lineage/freshness/health/card endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.provenance import SourceHealth

_CRITICAL = {"tesoreria_fx", "master_canal", "vendor_price_list"}


def compute_is_healthy(last_success, sla_minutes: int, *, now: datetime) -> bool:
    if last_success is None:
        return False
    return (now - last_success).total_seconds() / 60.0 < sla_minutes


def compute_is_stale(observed_at, valid_until, *, now: datetime) -> bool:
    if observed_at is None:
        return True
    if valid_until is not None and now > valid_until:
        return True
    return False


async def sources_health(session: AsyncSession) -> dict:
    now = datetime.now(UTC)
    rows = (await session.execute(select(SourceHealth))).scalars().all()
    items, blocking = [], []
    for r in rows:
        healthy = compute_is_healthy(r.last_sync_success_at, r.freshness_sla_minutes, now=now)
        age = (
            int((now - r.last_sync_success_at).total_seconds() / 60)
            if r.last_sync_success_at
            else None
        )
        items.append(
            {
                "source_op": r.source_op,
                "last_sync_attempt_at": r.last_sync_attempt_at,
                "last_sync_success_at": r.last_sync_success_at,
                "last_error": r.last_error,
                "freshness_sla_minutes": r.freshness_sla_minutes,
                "age_minutes": age,
                "is_healthy": healthy,
            }
        )
        if not healthy and r.source_op in _CRITICAL:
            blocking.append(r.source_op)
    return {"sources": items, "blocking": blocking}
