from __future__ import annotations

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin


class UnitTransform(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "unit_transforms"

    transform_type: Mapped[str] = mapped_column(Text, nullable=False)
    from_unit: Mapped[str] = mapped_column(Text, nullable=False)
    to_unit: Mapped[str] = mapped_column(Text, nullable=False)
    formula: Mapped[str | None] = mapped_column(Text)
    lookup_table: Mapped[dict | None] = mapped_column(JSONB)
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "transform_type IN ('numeric','lookup','nominal')",
            name="ck_unit_transforms_type",
        ),
    )


__all__ = ["UnitTransform"]
