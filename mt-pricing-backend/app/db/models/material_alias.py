"""MaterialAlias — tabla de homologación de materiales para el matching pipeline.

Mapea aliases industriales a un nombre canónico interno, permitiendo que el
scorer compare "SS316", "AISI 316", "1.4404" e "inox 316" como el mismo material.

Estructura:
  canonical_name  — clave interna única (ej. "stainless_steel_316")
  material_class  — metal | polymer | elastomer | composite
  display_name    — nombre legible (ej. "Stainless Steel 316")
  alias           — texto alternativo (ej. "SS316", "AISI 316")
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Index, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import UuidPkMixin

MATERIAL_CLASSES = ("metal", "polymer", "elastomer", "composite")


class MaterialAlias(UuidPkMixin, Base):
    __tablename__ = "material_aliases"

    canonical_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    material_class: Mapped[str] = mapped_column(String(16), nullable=False)
    alias: Mapped[str] = mapped_column(Text, nullable=False)
    alias_lower: Mapped[str] = mapped_column(Text, nullable=False)
    source: Mapped[str | None] = mapped_column(
        String(32), nullable=True,
        comment="industry_standard | amazon_pdp | erp | manual",
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    __table_args__ = (
        UniqueConstraint("canonical_name", "alias_lower", name="uq_material_alias_canonical_alias"),
        Index("idx_material_aliases_alias_lower", "alias_lower"),
        Index("idx_material_aliases_canonical", "canonical_name"),
    )
