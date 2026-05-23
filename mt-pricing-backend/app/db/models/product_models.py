"""ORM — product_models hierarchy: Series → ProductModel → Product (SKU).

product_models: numeric code (4295, 4097 …) + color variant pairing.
model_dimension_rows: per-DN dimensions as JSONB (schema varies by family).
model_flow_data: Kv/Cv + mesh per DN (strainers/filters only).
model_tech_tables: per-model P/T curves, materials matrix, etc.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class ProductModel(UuidPkMixin, Base):
    """Nivel modelo: code numérico que agrupa SKUs de la misma forma física.

    Ejemplo: code='4295', variant_of_id→ProductModel(code='40972') para
    la variante azul del mismo modelo rojo.
    """

    __tablename__ = "product_models"

    series_id: Mapped[UUID | None] = mapped_column(
        UUID_PG, ForeignKey("series.id", ondelete="RESTRICT"), nullable=True
    )
    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    color_label: Mapped[str | None] = mapped_column(String(32), nullable=True)
    connection_type: Mapped[str | None] = mapped_column(
        String(32),
        nullable=True,
        comment="thread_bsp | thread_bspt | thread_npt | flange_en | flange_ansi",
    )
    thread_standard: Mapped[str | None] = mapped_column(String(32), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    variant_of_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("product_models.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    variant_of: Mapped["ProductModel | None"] = relationship(
        "ProductModel", remote_side="ProductModel.id", foreign_keys=[variant_of_id]
    )
    dimension_rows: Mapped[list["ModelDimensionRow"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    flow_data: Mapped[list["ModelFlowData"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )
    tech_tables: Mapped[list["ModelTechTable"]] = relationship(
        back_populates="model", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("idx_product_models_series", "series_id"),
        Index("idx_product_models_variant_of", "variant_of_id"),
    )


class ModelDimensionRow(UuidPkMixin, Base):
    """Dimensiones por DN para un model — JSONB para soportar cualquier schema de familia.

    Schema ball valve: {"L_mm": 57, "H_mm": 72, "M_mm": 64}
    Schema fitting:    {"A_mm": 24, "C_mm": 15, "K_mm": 28, "D_mm": 12}
    Schema strainer:   {"L_mm": 130, "H_mm": 145, "ØD_mm": 95, "ØK_mm": 65}
    """

    __tablename__ = "model_dimension_rows"

    model_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("product_models.id", ondelete="CASCADE"), nullable=False
    )
    dn_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    dn_secondary_mm: Mapped[int | None] = mapped_column(
        Integer, nullable=True, comment="Solo para reductores (ej. reducción 1/2 x 3/8): DN salida"
    )
    dimensions: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'manual'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    model: Mapped[ProductModel] = relationship(back_populates="dimension_rows")

    __table_args__ = (
        UniqueConstraint("model_id", "dn_mm", "dn_secondary_mm", name="uq_model_dim_rows"),
        Index("idx_model_dim_rows_model", "model_id"),
        Index("idx_model_dim_rows_dn", "dn_mm"),
    )


class ModelFlowData(UuidPkMixin, Base):
    """Coeficientes de flujo Kv/Cv + malla por DN (filtros/coladores)."""

    __tablename__ = "model_flow_data"

    model_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("product_models.id", ondelete="CASCADE"), nullable=False
    )
    dn_mm: Mapped[int] = mapped_column(Integer, nullable=False)
    kv: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    cv: Mapped[float | None] = mapped_column(Numeric(10, 3), nullable=True)
    mesh_mm: Mapped[float | None] = mapped_column(
        Numeric(6, 2), nullable=True, comment="Tamaño de malla en mm (ej. 1.8, 1.0)"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    model: Mapped[ProductModel] = relationship(back_populates="flow_data")

    __table_args__ = (
        UniqueConstraint("model_id", "dn_mm", "mesh_mm", name="uq_model_flow"),
        Index("idx_model_flow_model", "model_id"),
    )


class ModelTechTable(UuidPkMixin, Base):
    """Tabla técnica a nivel modelo: curva P/T (por material junta), matriz materiales, etc.

    kind values: 'pt_curve' | 'materials_matrix' | 'dimensions_by_dn' | 'kv_table'
    Para curvas P/T con múltiples materiales de junta: una fila por material.
    data schema para pt_curve: [{"temperature_c": 20, "pressure_max_bar": 16}, ...]
    """

    __tablename__ = "model_tech_tables"

    model_id: Mapped[UUID] = mapped_column(
        UUID_PG, ForeignKey("product_models.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    gasket_material: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
        comment="Solo para kind=pt_curve con múltiples juntas: EPDM | PTFE | GRAFITO",
    )
    schema_version: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'v1'"))
    source: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'manual'"))
    data: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    model: Mapped[ProductModel] = relationship(back_populates="tech_tables")

    __table_args__ = (
        UniqueConstraint("model_id", "kind", "gasket_material", name="uq_model_tech_table"),
        Index("idx_model_tech_tables_model", "model_id"),
        Index("idx_model_tech_tables_kind", "kind"),
    )
