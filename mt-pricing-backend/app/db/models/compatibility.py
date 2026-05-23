"""ProductCompatibility — relaciones M:N de compatibilidad entre productos.

Almacena vínculos de tipo ``spare_part``, ``accessory``, ``replaces``,
``replaced_by`` y ``compatible_with`` entre SKUs del catálogo.

Notas de diseño:
- La relación es INTENCIONALMENTE unidireccional. Si el producto A es recambio
  de B, se almacena UNA fila (A → spare_part → B). La vista inversa (¿qué
  productos tienen A como recambio?) se resuelve por consulta, no por fila
  duplicada.
- Excepción: el par semántico ``replaces``/``replaced_by`` se mantiene
  sincronizado automáticamente en el servicio (CompatibilityService):
    * Añadir  A → replaces → B  crea también  B → replaced_by → A.
    * Eliminar A → replaces → B  borra también B → replaced_by → A.
- El constraint CHECK ``product_sku <> compatible_with_sku`` impide auto-enlaces.
- El UNIQUE ``(product_sku, compatible_with_sku, kind)`` impide duplicados.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin


class ProductCompatibility(UuidPkMixin, Base):
    """Fila de compatibilidad unidireccional entre dos SKUs."""

    __tablename__ = "product_compatibility"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    compatible_with_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey("products.sku", ondelete="CASCADE"),
        nullable=False,
    )
    # Usamos String en lugar de native Enum para evitar migraciones complejas
    # al añadir valores; el CHECK real está en la migración DDL.
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    position: Mapped[int] = mapped_column(
        SmallInteger,
        nullable=False,
        server_default=text("0"),
    )
    # Fase 5 — polymorphic owner: 'product' (default — vínculo SKU concreto),
    # 'variant' (futuro) o 'series' (vínculo a serie entera, normalmente
    # combinado con dn_min/dn_max para acotar el rango de calibres).
    owner_type: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        server_default=text("'product'"),
    )
    # Fase 5 — rango de DN aplicable. Si ambos NULL → aplica a cualquier calibre.
    # Si solo uno NULL → semi-acotado (≤ dn_max o ≥ dn_min).
    dn_min: Mapped[int | None] = mapped_column(Integer, nullable=True)
    dn_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("now()"),
    )
    created_by: Mapped[UUID | None] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )

    # --- relationships ---------------------------------------------------
    # `product` = el producto "origen" (el que tiene la compatibilidad).
    product: Mapped[Product] = relationship(  # type: ignore[name-defined]
        "Product",
        foreign_keys=[product_sku],
        back_populates="compatibilities_outgoing",
    )
    # `compatible_with` = el producto "destino" al que apunta el enlace.
    compatible_with: Mapped[Product] = relationship(  # type: ignore[name-defined]
        "Product",
        foreign_keys=[compatible_with_sku],
        back_populates="compatibilities_incoming",
    )

    __table_args__ = (
        CheckConstraint(
            "product_sku <> compatible_with_sku",
            name="chk_no_self_compatibility",
        ),
        CheckConstraint(
            "owner_type IN ('product','variant','series')",
            name="ck_product_compatibility_owner_type",
        ),
        CheckConstraint(
            "dn_min IS NULL OR dn_max IS NULL OR dn_max >= dn_min",
            name="ck_compat_dn_range",
        ),
        UniqueConstraint(
            "product_sku",
            "compatible_with_sku",
            "kind",
            name="uq_product_compatibility",
        ),
        Index("idx_product_compatibility_sku", "product_sku"),
        Index("idx_product_compatibility_with", "compatible_with_sku"),
        Index("idx_product_compatibility_kind", "kind"),
        Index("ix_compat_owner", "owner_type", "product_sku"),
    )
