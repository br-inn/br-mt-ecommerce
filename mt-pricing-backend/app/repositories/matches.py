"""MatchCandidateRepository — CRUD + filtros para `match_candidates`.

Cumple el contrato de :class:`BaseRepository` (PK UUID `id`). Métodos de
negocio:
- ``upsert_candidate`` — INSERT/UPDATE por ``(product_sku, channel, external_id)``.
- ``list_with_filters`` — paginación cursor-based para el endpoint
  ``GET /matches`` (sku, status, channel).
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select

from app.db.models.match_candidate import MatchCandidate
from app.repositories.base import BaseRepository


class MatchCandidateRepository(BaseRepository[MatchCandidate]):
    model = MatchCandidate
    pk_field = "id"
    soft_delete_field = None

    # ----------------------------------------------------------------------
    # Upsert
    # ----------------------------------------------------------------------
    async def find_by_external(
        self, product_sku: str, channel: str, external_id: str
    ) -> MatchCandidate | None:
        stmt = select(MatchCandidate).where(
            and_(
                MatchCandidate.product_sku == product_sku,
                MatchCandidate.channel == channel,
                MatchCandidate.external_id == external_id,
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def upsert_candidate(
        self,
        *,
        product_sku: str,
        channel: str,
        external_id: str,
        title: str,
        brand: str | None,
        price_aed: Any,
        delivery_text: str | None,
        specs_jsonb: dict[str, Any],
        kind: str,
        score: int,
        image_url: str | None = None,
        source_url: str | None = None,
        delivery_category: str | None = None,
        price_confidence_score: int | None = None,
        pack_units: int | None = None,
    ) -> MatchCandidate:
        existing = await self.find_by_external(product_sku, channel, external_id)
        if existing is not None:
            # Actualizamos campos volátiles; preservamos status/validation.
            existing.title = title
            existing.brand = brand
            existing.price_aed = price_aed
            existing.delivery_text = delivery_text
            existing.specs_jsonb = specs_jsonb
            existing.kind = kind
            existing.score = score
            existing.image_url = image_url
            existing.source_url = source_url
            existing.delivery_category = delivery_category
            existing.price_confidence_score = price_confidence_score
            existing.pack_units = pack_units
            await self.session.flush()
            await self.session.refresh(existing)
            return existing
        return await self.create(
            product_sku=product_sku,
            channel=channel,
            external_id=external_id,
            title=title,
            brand=brand,
            price_aed=price_aed,
            delivery_text=delivery_text,
            specs_jsonb=specs_jsonb,
            kind=kind,
            score=score,
            status="pending",
            image_url=image_url,
            source_url=source_url,
            delivery_category=delivery_category,
            price_confidence_score=price_confidence_score,
            pack_units=pack_units,
        )

    # ----------------------------------------------------------------------
    # Listing
    # ----------------------------------------------------------------------
    async def list_with_filters(
        self,
        *,
        sku: str | None = None,
        status: str | None = None,
        channel: str | None = None,
        cursor: UUID | None = None,
        limit: int = 50,
    ) -> tuple[Sequence[MatchCandidate], UUID | None]:
        stmt = select(MatchCandidate)
        if sku is not None:
            stmt = stmt.where(MatchCandidate.product_sku == sku)
        if status is not None:
            stmt = stmt.where(MatchCandidate.status == status)
        if channel is not None:
            stmt = stmt.where(MatchCandidate.channel == channel)
        if cursor is not None:
            stmt = stmt.where(MatchCandidate.id > cursor)
        stmt = stmt.order_by(MatchCandidate.score.desc(), MatchCandidate.id.asc()).limit(limit + 1)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        if len(rows) > limit:
            tail = rows[limit - 1]
            return rows[:limit], tail.id
        return rows, None

    # ----------------------------------------------------------------------
    # State transitions
    # ----------------------------------------------------------------------
    async def mark_validated(
        self, candidate_id: UUID, *, user_id: UUID | None
    ) -> MatchCandidate | None:
        obj = await self.get(candidate_id)
        if obj is None:
            return None
        obj.status = "validated"
        obj.validated_by = user_id
        obj.validated_at = datetime.now(tz=timezone.utc)
        obj.discarded_reason = None
        await self.session.flush()
        return obj

    async def mark_discarded(
        self,
        candidate_id: UUID,
        *,
        reason: str | None = None,
    ) -> MatchCandidate | None:
        obj = await self.get(candidate_id)
        if obj is None:
            return None
        obj.status = "discarded"
        obj.discarded_reason = reason
        await self.session.flush()
        return obj
