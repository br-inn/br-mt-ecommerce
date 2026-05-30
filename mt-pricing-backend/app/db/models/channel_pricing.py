"""ORM models for the channel pricing engine.

Seven tables: route params → channel fees → scheme configs →
product logistics → margin targets/overrides → scenarios.

Migration: 20260603_147_channel_pricing_engine.py
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
    Numeric,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ENUM as PG_ENUM
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.dialects.postgresql import UUID as UUID_PG_TYPE
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import UuidPkMixin
from app.db.types import UUID_PG

_SOURCE_OP = PG_ENUM(name="source_op", create_type=False)
_SNAPSHOT_KIND = PG_ENUM(name="snapshot_kind", create_type=False)


class TradeRouteParams(UuidPkMixin, Base):
    """Parámetros de ruta comercial (EUR→AED): FX, fletes, aranceles, etc.

    Una row por corredor logístico (p.ej. 'es_to_uae').
    """

    __tablename__ = "trade_route_params"

    route_code: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    fx_rate: Mapped[Decimal] = mapped_column(Numeric(10, 6), nullable=False)
    fx_buffer_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("2")
    )
    freight_rate_per_kg: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default=text("0")
    )
    freight_min_aed: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, server_default=text("0")
    )
    import_tariff_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("4.14")
    )
    local_warehouse_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("2")
    )
    handling_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("1.5")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_trade_route_params_updated_by", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_trade_route_params_created_by", ondelete="SET NULL"),
        nullable=True,
    )
    source_op: Mapped[str] = mapped_column(
        _SOURCE_OP, nullable=False, server_default=text("'manual'")
    )
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    override_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_trade_route_params_override_by", ondelete="SET NULL"),
        nullable=True,
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class ChannelFeeParams(UuidPkMixin, Base):
    """Comisiones y fees del canal (por canal, 1:1 con channels).

    Incluye descuento MT, comisión del canal, IVA, publicidad, devoluciones
    y multiplicador de almacenamiento.
    """

    __tablename__ = "channel_fee_params"

    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("channels.id", name="fk_channel_fee_params_channel"),
        nullable=False,
        unique=True,
    )
    route_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("trade_route_params.id", name="fk_channel_fee_params_route"),
        nullable=False,
    )
    mt_discount_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("15")
    )
    commission_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("11")
    )
    vat_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("5")
    )
    advertising_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("8")
    )
    returns_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("2")
    )
    storage_multiplier: Mapped[Decimal] = mapped_column(
        Numeric(6, 4), nullable=False, server_default=text("1.0")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_fee_params_updated_by", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_fee_params_created_by", ondelete="SET NULL"),
        nullable=True,
    )
    source_op: Mapped[str] = mapped_column(
        _SOURCE_OP, nullable=False, server_default=text("'manual'")
    )
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    override_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_fee_params_override_by", ondelete="SET NULL"),
        nullable=True,
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    route: Mapped[TradeRouteParams] = relationship(
        "TradeRouteParams",
        foreign_keys=[route_id],
        lazy="raise",
    )

    __table_args__ = (Index("idx_channel_fee_params_channel", "channel_id"),)


class ChannelSchemeParams(UuidPkMixin, Base):
    """Configuración por (canal, fulfillment_scheme): disponibilidad y suplementos."""

    __tablename__ = "channel_scheme_params"

    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("channels.id", name="fk_channel_scheme_params_channel"),
        nullable=False,
    )
    fulfillment_scheme: Mapped[str] = mapped_column(
        PG_ENUM(
            "canal_full",
            "canal_lastmile",
            "merchant_managed",
            name="fulfillment_scheme",
            create_type=False,
        ),
        nullable=False,
    )
    scheme_label: Mapped[str] = mapped_column(Text, nullable=False)
    is_available: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    flat_supplement_aed: Mapped[Decimal] = mapped_column(
        Numeric(8, 2), nullable=False, server_default=text("0")
    )
    pct_surcharge: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("0")
    )
    max_weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))

    __table_args__ = (
        UniqueConstraint("channel_id", "fulfillment_scheme", name="uq_channel_scheme_params"),
        Index("idx_channel_scheme_params_lookup", "channel_id", "fulfillment_scheme"),
    )


class ChannelProductLogistics(UuidPkMixin, Base):
    """Fees logísticos por (producto, canal): inbound, storage, fulfillment."""

    __tablename__ = "channel_product_logistics"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            "products.sku",
            ondelete="CASCADE",
            name="fk_channel_product_logistics_sku",
        ),
        nullable=False,
    )
    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("channels.id", name="fk_channel_product_logistics_channel"),
        nullable=False,
    )
    inbound_fee_aed: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default=text("0")
    )
    storage_fee_aed: Mapped[Decimal] = mapped_column(
        Numeric(10, 4), nullable=False, server_default=text("0")
    )
    fulfillment_fee_aed: Mapped[Decimal] = mapped_column(
        Numeric(8, 4), nullable=False, server_default=text("0")
    )
    default_scheme: Mapped[str] = mapped_column(
        PG_ENUM(
            "canal_full",
            "canal_lastmile",
            "merchant_managed",
            name="fulfillment_scheme",
            create_type=False,
        ),
        nullable=False,
        server_default=text("'canal_full'"),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_product_logistics_updated_by", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_product_logistics_created_by", ondelete="SET NULL"),
        nullable=True,
    )
    source_op: Mapped[str] = mapped_column(
        _SOURCE_OP, nullable=False, server_default=text("'manual'")
    )
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    override_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey(
            "users.id", name="fk_channel_product_logistics_override_by", ondelete="SET NULL"
        ),
        nullable=True,
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("product_sku", "channel_id", name="uq_channel_product_logistics"),
        Index("idx_channel_product_logistics_sku_ch", "product_sku", "channel_id"),
        Index("idx_channel_product_logistics_channel", "channel_id"),
    )


class ChannelMarginTarget(UuidPkMixin, Base):
    """Margen objetivo por (canal, familia, modelo de venta)."""

    __tablename__ = "channel_margin_targets"

    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("channels.id", name="fk_channel_margin_targets_channel"),
        nullable=False,
    )
    family_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("families.id", name="fk_channel_margin_targets_family"),
        nullable=False,
    )
    selling_model: Mapped[str] = mapped_column(
        PG_ENUM("b2c", "b2b", name="selling_model", create_type=False),
        nullable=False,
        server_default=text("'b2c'"),
    )
    margin_target_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, server_default=text("12")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    updated_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_margin_targets_updated_by", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_margin_targets_created_by", ondelete="SET NULL"),
        nullable=True,
    )
    source_op: Mapped[str] = mapped_column(
        _SOURCE_OP, nullable=False, server_default=text("'manual'")
    )
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    override_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_margin_targets_override_by", ondelete="SET NULL"),
        nullable=True,
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "channel_id", "family_id", "selling_model", name="uq_channel_margin_targets"
        ),
        Index(
            "idx_channel_margin_targets_lookup",
            "channel_id",
            "family_id",
            "selling_model",
        ),
    )


class ChannelMarginOverride(UuidPkMixin, Base):
    """Override de margen por (producto, canal, modelo de venta)."""

    __tablename__ = "channel_margin_overrides"

    product_sku: Mapped[str] = mapped_column(
        Text,
        ForeignKey(
            "products.sku",
            ondelete="CASCADE",
            name="fk_channel_margin_overrides_sku",
        ),
        nullable=False,
    )
    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("channels.id", name="fk_channel_margin_overrides_channel"),
        nullable=False,
    )
    selling_model: Mapped[str] = mapped_column(
        PG_ENUM("b2c", "b2b", name="selling_model", create_type=False),
        nullable=False,
        server_default=text("'b2c'"),
    )
    margin_override_pct: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_margin_overrides_created_by", ondelete="SET NULL"),
        nullable=True,
    )
    source_op: Mapped[str] = mapped_column(
        _SOURCE_OP, nullable=False, server_default=text("'manual'")
    )
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)
    observed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    override_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_channel_margin_overrides_override_by", ondelete="SET NULL"),
        nullable=True,
    )
    override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "product_sku",
            "channel_id",
            "selling_model",
            name="uq_channel_margin_overrides",
        ),
        Index(
            "idx_channel_margin_overrides_sku",
            "product_sku",
            "channel_id",
            "selling_model",
        ),
    )


class PricingScenario(UuidPkMixin, Base):
    """Escenario de pricing A/B por (canal, modelo de venta).

    `slot` = 'A' o 'B'. `config_jsonb` guarda snapshot de parámetros del motor.
    """

    __tablename__ = "pricing_scenarios"

    channel_id: Mapped[UUID] = mapped_column(
        UUID_PG,
        ForeignKey("channels.id", name="fk_pricing_scenarios_channel"),
        nullable=False,
    )
    selling_model: Mapped[str] = mapped_column(
        PG_ENUM("b2c", "b2b", name="selling_model", create_type=False),
        nullable=False,
        server_default=text("'b2c'"),
    )
    slot: Mapped[str] = mapped_column(CHAR(1), nullable=False)
    label: Mapped[str | None] = mapped_column(Text)
    config_jsonb: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'::jsonb")
    )
    snapshot_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
    created_by: Mapped[UUID | None] = mapped_column(
        UUID_PG,
        ForeignKey("users.id", name="fk_pricing_scenarios_created_by", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(
        _SNAPSHOT_KIND, nullable=False, server_default=text("'manual_a'")
    )
    retention_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        CheckConstraint("slot IN ('A','B')", name="ck_pricing_scenarios_slot"),
        Index(
            "uq_pricing_scenarios_manual",
            "channel_id",
            "selling_model",
            "slot",
            unique=True,
            postgresql_where=text("kind IN ('manual_a','manual_b')"),
        ),
        Index("idx_pricing_scenarios_lookup", "channel_id", "selling_model"),
        Index(
            "idx_pricing_scenarios_retention",
            "retention_until",
            postgresql_where=text("retention_until IS NOT NULL"),
        ),
    )


__all__ = [
    "ChannelFeeParams",
    "ChannelMarginOverride",
    "ChannelMarginTarget",
    "ChannelProductLogistics",
    "ChannelSchemeParams",
    "PricingScenario",
    "TradeRouteParams",
]
