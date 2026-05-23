from __future__ import annotations
from uuid import UUID
from sqlalchemy import CheckConstraint, ForeignKey, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin
from app.db.types import UUID_PG


class RuleSuggestion(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "rule_suggestions"

    taxonomy_profile_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("taxonomy_profiles.id", ondelete="SET NULL"), nullable=True
    )
    suggestion_type: Mapped[str] = mapped_column(Text, nullable=False)
    analysis_summary: Mapped[str | None] = mapped_column(Text)
    proposed_change: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'pending'"))

    __table_args__ = (
        CheckConstraint(
            "suggestion_type IN ('false_positive','false_negative','slow_confirmation')",
            name="ck_rule_suggestion_type",
        ),
        CheckConstraint(
            "status IN ('pending','applied','dismissed')",
            name="ck_rule_suggestion_status",
        ),
    )
