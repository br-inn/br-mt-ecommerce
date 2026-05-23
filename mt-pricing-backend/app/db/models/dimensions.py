"""ORM models — Fase 3 tablas técnicas granulares (PDF §9).

Modelo:

- ``ActuationCode``: catálogo canónico (free / handle / MR / motor / pneu).
  Referenciado por ``DimensionRow.actuation_code_id``.

- ``Standard``: catálogo de normas (ASTM/EN/ISO/…). Si ``material_components``
  existe, se vincula via ``standard_id``. (No modelamos la relación reversa
  aquí — vive en el modelo material_components, fuera de este módulo.)

- ``DimensionColumn``: definición de columna (DN, A, B, H, F…) por familia.
  Reutilizable entre productos de la misma family. UNIQUE(family_id, code).

- ``DimensionRow``: fila por producto (un tamaño / variante). Soporta DN
  numérico para filtrado y ``actuation_code_id`` para discriminar variante
  de actuación dentro del mismo tamaño.

- ``DimensionCell``: celda intersección row × column. UNIQUE(row, column).
  CHECK garantiza ``value_number IS NOT NULL OR value_text IS NOT NULL``.

- ``PressureTemperaturePoint``: punto de curva P-T por producto, con
  ``series_variant_code`` opcional para discriminar curvas.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


# ---------------------------------------------------------------------------
# 1. ActuationCode
# ---------------------------------------------------------------------------
class ActuationCode(UuidPkMixin, Base):
    """Código canónico de actuación (free/handle/MR/motor/pneu)."""

    __tablename__ = "actuation_codes"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    name_en: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (
        CheckConstraint(
            "type IN ('free_shaft','handle','gearbox','motorized','pneumatic')",
            name="ck_actuation_codes_type",
        ),
    )


# ---------------------------------------------------------------------------
# 2. Standard
# ---------------------------------------------------------------------------
class Standard(UuidPkMixin, Base):
    """Norma técnica (ASTM/EN/ISO/…) con edición y URL de referencia."""

    __tablename__ = "standards"

    code: Mapped[str] = mapped_column(Text, nullable=False)
    edition: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("''"))
    title_en: Mapped[str] = mapped_column(Text, nullable=False)
    reference_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (UniqueConstraint("code", "edition", name="uq_standards_code_edition"),)


# ---------------------------------------------------------------------------
# 3. DimensionColumn
# ---------------------------------------------------------------------------
class DimensionColumn(UuidPkMixin, Base):
    """Definición de columna por familia (DN, A, B, H, F, peso…)."""

    __tablename__ = "dimension_columns"

    family_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    label_en: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    cells: Mapped[list["DimensionCell"]] = relationship(
        back_populates="column",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint("family_id", "code", name="uq_dimension_columns_family_code"),
        Index("ix_dimension_columns_family", "family_id"),
    )


# ---------------------------------------------------------------------------
# 4. DimensionRow
# ---------------------------------------------------------------------------
class DimensionRow(UuidPkMixin, Base):
    """Fila de dimensión por producto (tamaño / variante de actuación)."""

    __tablename__ = "dimension_rows"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    size_label: Mapped[str | None] = mapped_column(Text, nullable=True)
    dn: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actuation_code_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("actuation_codes.id", ondelete="SET NULL"),
        nullable=True,
    )
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    actuation_code: Mapped[ActuationCode | None] = relationship(
        foreign_keys=[actuation_code_id], lazy="joined"
    )
    cells: Mapped[list["DimensionCell"]] = relationship(
        back_populates="row",
        cascade="all, delete-orphan",
        order_by="DimensionCell.column_id",
    )

    __table_args__ = (Index("ix_dr_product", "product_sku"),)


# ---------------------------------------------------------------------------
# 5. DimensionCell
# ---------------------------------------------------------------------------
class DimensionCell(UuidPkMixin, Base):
    """Celda valor en la intersección row × column."""

    __tablename__ = "dimension_cells"

    row_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("dimension_rows.id", ondelete="CASCADE"),
        nullable=False,
    )
    column_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("dimension_columns.id", ondelete="RESTRICT"),
        nullable=False,
    )
    value_number: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    row: Mapped[DimensionRow] = relationship(back_populates="cells")
    column: Mapped[DimensionColumn] = relationship(back_populates="cells")

    __table_args__ = (
        UniqueConstraint("row_id", "column_id", name="uq_dimension_cells_row_col"),
        CheckConstraint(
            "value_number IS NOT NULL OR value_text IS NOT NULL",
            name="ck_dimension_cells_value_present",
        ),
        Index("ix_dc_row", "row_id"),
        Index("ix_dc_column", "column_id"),
    )


# ---------------------------------------------------------------------------
# 6. PressureTemperaturePoint
# ---------------------------------------------------------------------------
class PressureTemperaturePoint(UuidPkMixin, Base):
    """Punto de la curva presión-temperatura para un producto."""

    __tablename__ = "pressure_temperature_points"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    series_variant_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperature_c: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    pressure_max_bar: Mapped[Decimal] = mapped_column(Numeric(8, 2), nullable=False)
    condition_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )

    __table_args__ = (Index("ix_ptp_product", "product_sku"),)
