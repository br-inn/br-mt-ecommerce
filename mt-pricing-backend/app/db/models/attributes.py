"""ORM models — Fase 2 EAV typed attribute system (PDF §8 alignment).

Tablas:
- ``AttributeDefinition``: catálogo central de atributos disponibles.
  Cada uno tiene ``data_type`` (number/integer/text/bool/enum/range/dimension)
  + flags ``is_filterable`` y ``is_seo_relevant`` + ``scope`` (product/variant/both).
- ``AttributeOption``: opciones discretas para atributos tipo enum.
- ``FamilyAttribute``: plantilla por familia — qué atributos aplican a qué
  familia, en qué grupo visual, en qué orden, requerido o no.
- ``AttributeValue``: valores reales asignados a un producto/variante.
  ``owner_type`` polimórfico (product|variant), ``owner_id`` TEXT (porque
  ``products.sku`` es TEXT PK). Una sola fila por (owner, attribute,
  language) con un campo tipado relleno.

NOTAS:
- ``products.specs`` JSONB se mantiene como escape hatch (decisión §5.7 audit).
- Todos los identifiers en inglés; i18n via filas separadas + ``language``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CHAR,
    Boolean,
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
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG


class AttributeDefinition(UuidPkMixin, Base):
    """Catálogo central de atributos disponibles para EAV."""

    __tablename__ = "attribute_definitions"

    code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    label_en: Mapped[str] = mapped_column(Text, nullable=False)
    data_type: Mapped[str] = mapped_column(Text, nullable=False)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    description_en: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_filterable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    is_seo_relevant: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    scope: Mapped[str] = mapped_column(Text, nullable=False, server_default=text("'product'"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )

    options: Mapped[list[AttributeOption]] = relationship(
        back_populates="attribute",
        cascade="all, delete-orphan",
        order_by="AttributeOption.order_index",
    )
    family_links: Mapped[list[FamilyAttribute]] = relationship(
        back_populates="attribute",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        CheckConstraint(
            "data_type IN ('number','integer','text','bool','enum','range','dimension')",
            name="ck_attribute_definitions_data_type",
        ),
        CheckConstraint(
            "scope IN ('product','variant','both')",
            name="ck_attribute_definitions_scope",
        ),
    )


class AttributeOption(UuidPkMixin, Base):
    """Opciones discretas para atributos tipo enum."""

    __tablename__ = "attribute_options"

    attribute_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("attribute_definitions.id", ondelete="CASCADE"),
        nullable=False,
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    label_en: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))

    attribute: Mapped[AttributeDefinition] = relationship(back_populates="options")

    __table_args__ = (
        UniqueConstraint("attribute_id", "code", name="uq_attribute_options_attr_code"),
        Index("ix_attribute_options_attribute", "attribute_id"),
    )


class FamilyAttribute(UuidPkMixin, Base):
    """Plantilla por familia — qué atributos aplican a qué family."""

    __tablename__ = "family_attributes"

    family_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("families.id", ondelete="CASCADE"),
        nullable=False,
    )
    attribute_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    group_code: Mapped[str] = mapped_column(Text, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("false"))
    default_value: Mapped[str | None] = mapped_column(Text, nullable=True)
    validation_rule: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    attribute: Mapped[AttributeDefinition] = relationship(back_populates="family_links")

    __table_args__ = (
        UniqueConstraint("family_id", "attribute_id", name="uq_family_attributes_family_attr"),
        Index("ix_fa_family", "family_id"),
        Index("ix_fa_attribute", "attribute_id"),
    )


class AttributeValue(UuidPkMixin, Base):
    """Valor real asignado a un product/variant para un atributo."""

    __tablename__ = "attribute_values"

    owner_type: Mapped[str] = mapped_column(Text, nullable=False)
    # TEXT porque products.sku es TEXT PK; variants también usarán sku TEXT.
    owner_id: Mapped[str] = mapped_column(Text, nullable=False)
    attribute_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("attribute_definitions.id", ondelete="RESTRICT"),
        nullable=False,
    )

    value_number: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    value_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    value_bool: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    value_enum_id: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("attribute_options.id", ondelete="RESTRICT"),
        nullable=True,
    )
    value_min: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    value_max: Mapped[Decimal | None] = mapped_column(Numeric(18, 6), nullable=True)
    unit: Mapped[str | None] = mapped_column(Text, nullable=True)
    language: Mapped[str | None] = mapped_column(CHAR(2), nullable=True)

    attribute: Mapped[AttributeDefinition] = relationship()
    enum_option: Mapped[AttributeOption | None] = relationship(foreign_keys=[value_enum_id])

    __table_args__ = (
        UniqueConstraint(
            "owner_type",
            "owner_id",
            "attribute_id",
            "language",
            name="uq_attribute_values_owner_attr_lang",
        ),
        CheckConstraint(
            "owner_type IN ('product','variant')",
            name="ck_attribute_values_owner_type",
        ),
        CheckConstraint(
            "("
            "(value_number IS NOT NULL)::int + "
            "(value_text IS NOT NULL)::int + "
            "(value_bool IS NOT NULL)::int + "
            "(value_enum_id IS NOT NULL)::int + "
            "((value_min IS NOT NULL) OR (value_max IS NOT NULL))::int"
            ") >= 1",
            name="ck_attribute_values_at_least_one_value",
        ),
        Index("ix_av_owner", "owner_type", "owner_id"),
        Index("ix_av_attribute", "attribute_id"),
    )
