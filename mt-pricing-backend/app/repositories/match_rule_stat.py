from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import func, select

from app.db.models.match_candidate import MatchCandidate
from app.db.models.match_rule_stat import MatchRuleStat
from app.repositories.base import BaseRepository


class MatchRuleStatRepository(BaseRepository[MatchRuleStat]):
    model = MatchRuleStat
    pk_field = "id"
    soft_delete_field = None

    async def get_profile_metrics(self, taxonomy_profile_id: UUID, days: int = 30) -> dict:
        since = datetime.now(UTC) - timedelta(days=days)

        total_stmt = select(func.count(MatchRuleStat.id)).where(
            MatchRuleStat.taxonomy_profile_id == taxonomy_profile_id,
            MatchRuleStat.created_at >= since,
        )
        total = (await self.session.execute(total_stmt)).scalar_one() or 0

        confirmed_stmt = (
            select(func.count(MatchCandidate.id))
            .join(MatchRuleStat, MatchRuleStat.match_candidate_id == MatchCandidate.id)
            .where(
                MatchRuleStat.taxonomy_profile_id == taxonomy_profile_id,
                MatchRuleStat.created_at >= since,
                MatchCandidate.label == "accept",
            )
        )
        confirmed = (await self.session.execute(confirmed_stmt)).scalar_one() or 0

        rejected_stmt = (
            select(func.count(MatchCandidate.id))
            .join(MatchRuleStat, MatchRuleStat.match_candidate_id == MatchCandidate.id)
            .where(
                MatchRuleStat.taxonomy_profile_id == taxonomy_profile_id,
                MatchRuleStat.created_at >= since,
                MatchCandidate.label == "reject",
            )
        )
        rejected = (await self.session.execute(rejected_stmt)).scalar_one() or 0

        reviewed = confirmed + rejected
        confirmation_rate = round(confirmed / reviewed, 3) if reviewed > 0 else None
        fp_rate = round(rejected / reviewed, 3) if reviewed > 0 else None

        return {
            "total_matches": total,
            "confirmed": confirmed,
            "rejected": rejected,
            "confirmation_rate": confirmation_rate,
            "fp_rate": fp_rate,
            "days": days,
        }
