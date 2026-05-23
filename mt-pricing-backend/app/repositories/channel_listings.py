"""Repositorio para ``channel_listings`` y ``channel_sync_events``.

No commitea — la session es responsabilidad del caller.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.channel_listing import ChannelListing, ChannelSyncEvent


class ChannelListingRepository:
    """CRUD básico + queries por (channel_code, sku)."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, listing_id: UUID) -> ChannelListing | None:
        return await self.session.get(ChannelListing, listing_id)

    async def get_by_channel_sku(self, channel_code: str, sku: str) -> ChannelListing | None:
        stmt = select(ChannelListing).where(
            ChannelListing.channel_code == channel_code,
            ChannelListing.product_sku == sku,
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_channel(
        self,
        channel_code: str,
        *,
        cursor: str | None = None,
        limit: int = 50,
        diff_status: str | None = None,
    ) -> tuple[Sequence[ChannelListing], str | None]:
        """Cursor pagination ordenada por product_sku ASC.

        ``diff_status`` opcional filtra por la summary persistida (drift,
        missing, queued > 0). ``"clean"`` → solo los que tienen únicamente
        match (drift=0, missing=0, queued=0).
        """
        stmt = select(ChannelListing).where(ChannelListing.channel_code == channel_code)
        if cursor:
            stmt = stmt.where(ChannelListing.product_sku > cursor)
        # Filtrado client-side over JSONB summary — para Sprint 3 OK; futuro
        # crear índice GIN sobre diff_summary si rendimiento se vuelve un
        # cuello de botella.
        stmt = stmt.order_by(ChannelListing.product_sku.asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())

        if diff_status is not None:
            rows = [r for r in rows if _matches_status(r.diff_summary, diff_status)]

        next_cursor: str | None = None
        if len(rows) > limit:
            next_cursor = rows[limit - 1].product_sku
            rows = rows[:limit]
        return rows, next_cursor

    async def upsert(
        self,
        *,
        channel_code: str,
        product_sku: str,
        external_id: str,
        canonical_snapshot: dict[str, Any],
        live_snapshot: dict[str, Any],
        diff_summary: dict[str, Any],
        buybox_state: str = "none",
        buybox_pct_7d: float | None = None,
        stock_qty: int | None = None,
        rating: float | None = None,
        reviews_count: int | None = None,
        last_sync_at: datetime | None = None,
    ) -> ChannelListing:
        existing = await self.get_by_channel_sku(channel_code, product_sku)
        if existing is None:
            obj = ChannelListing(
                channel_code=channel_code,
                product_sku=product_sku,
                external_id=external_id,
                canonical_snapshot_jsonb=canonical_snapshot,
                live_snapshot_jsonb=live_snapshot,
                diff_summary=diff_summary,
                buybox_state=buybox_state,
                buybox_pct_7d=buybox_pct_7d,
                stock_qty=stock_qty,
                rating=rating,
                reviews_count=reviews_count,
                last_sync_at=last_sync_at,
            )
            self.session.add(obj)
            await self.session.flush()
            return obj

        existing.external_id = external_id
        existing.canonical_snapshot_jsonb = canonical_snapshot
        existing.live_snapshot_jsonb = live_snapshot
        existing.diff_summary = diff_summary
        existing.buybox_state = buybox_state
        existing.buybox_pct_7d = buybox_pct_7d
        existing.stock_qty = stock_qty
        existing.rating = rating
        existing.reviews_count = reviews_count
        existing.last_sync_at = last_sync_at
        await self.session.flush()
        return existing


class ChannelSyncEventRepository:
    """Append-only para channel_sync_events."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def log(
        self,
        *,
        channel_code: str,
        event_type: str,
        ok: bool,
        product_sku: str | None = None,
        summary: str | None = None,
        payload: dict[str, Any] | None = None,
        duration_ms: int | None = None,
    ) -> ChannelSyncEvent:
        evt = ChannelSyncEvent(
            channel_code=channel_code,
            event_type=event_type,
            ok=ok,
            product_sku=product_sku,
            summary=summary,
            payload_jsonb=payload or {},
            duration_ms=duration_ms,
        )
        self.session.add(evt)
        await self.session.flush()
        return evt

    async def recent(self, channel_code: str, *, limit: int = 50) -> Sequence[ChannelSyncEvent]:
        stmt = (
            select(ChannelSyncEvent)
            .where(ChannelSyncEvent.channel_code == channel_code)
            .order_by(desc(ChannelSyncEvent.created_at))
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


def _matches_status(summary: dict[str, Any], target: str) -> bool:
    """Helper para filtrar listings por summary."""
    if not isinstance(summary, dict):
        return False
    if target == "clean":
        return all(int(summary.get(k, 0) or 0) == 0 for k in ("drift", "missing", "queued"))
    return int(summary.get(target, 0) or 0) > 0


__all__ = [
    "ChannelListingRepository",
    "ChannelSyncEventRepository",
]
