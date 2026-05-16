"""TaxonomyProfile — perfiles de pesos y hard blockers por familia para el rule engine.

Cada fila define cómo se pondera cada dimensión de matching para una familia
de productos (ball_valve, pressure_gauge, etc.) y qué condiciones son
hard blockers (rechazo automático del match).

El perfil ``_default`` se usa cuando no existe uno específico para la familia.
"""
from __future__ import annotations

from sqlalchemy import CheckConstraint, Text, text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin


class TaxonomyProfile(UuidPkMixin, TimestampMixin, Base):
    """Una fila = un perfil de matching para una familia de productos."""

    __tablename__ = "taxonomy_profiles"

    family: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    weights: Mapped[dict] = mapped_column(JSONB, nullable=False)
    hard_blockers: Mapped[list] = mapped_column(
        ARRAY(Text),
        nullable=False,
        server_default=text("'{}'::text[]"),
    )
    description: Mapped[str | None] = mapped_column(Text)

    __table_args__ = (
        CheckConstraint("family != ''", name="ck_taxonomy_profiles_family_nonempty"),
    )


__all__ = ["TaxonomyProfile"]
