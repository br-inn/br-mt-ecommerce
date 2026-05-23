from __future__ import annotations

from uuid import UUID

from sqlalchemy import select

from app.db.models.rule_suggestion import RuleSuggestion
from app.repositories.base import BaseRepository


class RuleSuggestionRepository(BaseRepository[RuleSuggestion]):
    model = RuleSuggestion
    pk_field = "id"
    soft_delete_field = None

    async def list_pending_for_profile(self, taxonomy_profile_id: UUID) -> list[RuleSuggestion]:
        stmt = (
            select(RuleSuggestion)
            .where(
                RuleSuggestion.taxonomy_profile_id == taxonomy_profile_id,
                RuleSuggestion.status == "pending",
            )
            .order_by(RuleSuggestion.created_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def has_pending_for_type(self, taxonomy_profile_id: UUID, suggestion_type: str) -> bool:
        stmt = select(RuleSuggestion.id).where(
            RuleSuggestion.taxonomy_profile_id == taxonomy_profile_id,
            RuleSuggestion.suggestion_type == suggestion_type,
            RuleSuggestion.status == "pending",
        )
        result = await self.session.execute(stmt)
        return result.first() is not None
