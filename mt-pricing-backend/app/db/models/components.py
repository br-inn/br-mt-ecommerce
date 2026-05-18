"""Wave 3 ORM — product_materials + product_connections (multi-componente)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    String,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if False:  # TYPE_CHECKING
    from app.db.models.product import Product


class ProductMaterial(Base):
    """Material por componente del producto.

    Composite PK = (product_sku, component, position).
    Un trigger DB sincroniza ``products.material`` con ``body[position=0]``.
    """

    __tablename__ = "product_materials"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        primary_key=True,
    )
    component: Mapped[str] = mapped_column(
        Enum(
            "body", "closure", "seat", "gasket", "screen",
            "actuator_housing", "stem", "handle", "other",
            name="component_kind",
            create_type=False,
        ),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(
        SmallInteger,
        primary_key=True,
        server_default=text("0"),
    )
    material: Mapped[str] = mapped_column(Text, nullable=False)
    observations: Mapped[str | None] = mapped_column(Text)
    material_grade: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="ej. EN-GJL-250, AISI 304, CW617N"
    )
    material_standard: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="ej. ASTM A307, UNE-EN-12165"
    )
    surface_treatment: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="ej. Epoxy, Nickel, Zinc, None"
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    product: Mapped["Product"] = relationship(back_populates="materials")

    __table_args__ = (
        Index("idx_product_materials_sku", "product_sku"),
        Index("idx_product_materials_material", "material"),
        Index("idx_product_materials_component", "component"),
    )


class ProductConnection(Base):
    """Conexión del producto (puerto físico). Composite PK = (product_sku, position)."""

    __tablename__ = "product_connections"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        primary_key=True,
    )
    position: Mapped[int] = mapped_column(SmallInteger, primary_key=True)
    connection_type: Mapped[str] = mapped_column(String(32), nullable=False)
    dn: Mapped[str | None] = mapped_column(Text)
    dn_real: Mapped[str | None] = mapped_column(Text)
    size: Mapped[str | None] = mapped_column(Text)
    threading: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
        onupdate=text("now()"),
    )

    product: Mapped["Product"] = relationship(back_populates="connections")

    __table_args__ = (
        CheckConstraint("position >= 1 AND position <= 8", name="chk_connection_position"),
        Index("idx_product_connections_sku", "product_sku"),
        Index("idx_product_connections_type", "connection_type"),
        Index("idx_product_connections_dn", "dn"),
    )
