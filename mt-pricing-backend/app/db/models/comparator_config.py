from __future__ import annotations

from sqlalchemy import Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin


class ComparatorConfig(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "comparator_config"

    key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    value: Mapped[dict] = mapped_column(JSONB, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)


__all__ = ["ComparatorConfig"]
