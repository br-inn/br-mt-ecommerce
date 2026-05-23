from __future__ import annotations

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin


class NormEquivalence(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "norm_equivalences"

    norm_a: Mapped[str] = mapped_column(Text, nullable=False)
    system_a: Mapped[str] = mapped_column(Text, nullable=False)
    norm_b: Mapped[str] = mapped_column(Text, nullable=False)
    system_b: Mapped[str] = mapped_column(Text, nullable=False)
    equivalence_type: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint(
            "equivalence_type IN ('exact','subset','compatible')",
            name="ck_norm_equiv_type",
        ),
    )
