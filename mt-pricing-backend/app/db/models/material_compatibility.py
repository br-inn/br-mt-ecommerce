"""MaterialCompatibility — tabla referencial de compatibilidades materiales × T °C.

Persiste el contenido del Excel ``Copia de Compatibilidad de Materiales MT
V4.xlsx`` (~657 filas). Se consume desde el matching pipeline (US-1A-09-01-S3,
Etapa 4 hard rules — ``are_materials_compatible``).

Schema:
- ``id`` UUID PK.
- ``producto_descriptor`` TEXT NOT NULL — texto del Excel original (ej.
  "Ácido sulfúrico 98%").
- ``temperatura_c`` NUMERIC NOT NULL.
- ``compatibilities`` JSONB NOT NULL DEFAULT '{}' con
  ``{material_name: flag}`` (flag normalizado: "ok", "x", "-").
- Índices: ``(producto_descriptor, temperatura_c)`` UNIQUE — clave natural.

NO se expone vía API en S3 (consumo interno). UI tab Compatibilidades en S4.
"""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import (
    Index,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import TimestampMixin, UuidPkMixin


class MaterialCompatibility(UuidPkMixin, TimestampMixin, Base):
    __tablename__ = "material_compatibilities"

    producto_descriptor: Mapped[str] = mapped_column(Text, nullable=False)
    temperatura_c: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    compatibilities: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )

    __table_args__ = (
        UniqueConstraint(
            "producto_descriptor",
            "temperatura_c",
            name="uq_material_compatibilities_descriptor_temp",
        ),
        Index(
            "idx_material_compatibilities_descriptor",
            "producto_descriptor",
        ),
    )
