from __future__ import annotations
from uuid import UUID
from sqlalchemy import ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG


class MatchRuleStat(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "match_rule_stats"

    match_candidate_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("match_candidates.id", ondelete="CASCADE"), nullable=False
    )
    taxonomy_profile_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("taxonomy_profiles.id", ondelete="SET NULL"), nullable=True
    )
    score_breakdown: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    dimensions_fired: Mapped[list] = mapped_column(
        ARRAY(Text), nullable=False, server_default=text("'{}'::text[]")
    )
