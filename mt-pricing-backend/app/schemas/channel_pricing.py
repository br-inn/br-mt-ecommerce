"""Pydantic schemas for the channel pricing engine API.

Covers: TradeRouteParams, ChannelFeeParams, ChannelSchemeParams,
ChannelProductLogistics, ChannelMarginTarget, ChannelMarginOverride,
PricingScenario, plus import/batch helpers.
"""

from __future__ import annotations

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.db.enums import CeilingBasis, FulfillmentScheme, SellingModel


# ── Trade Route Params ────────────────────────────────────────────────


class TradeRouteParamsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    route_code: str
    description: str | None
    fx_rate: Decimal
    fx_buffer_pct: Decimal
    freight_rate_per_kg: Decimal
    freight_min_aed: Decimal
    import_tariff_pct: Decimal
    local_warehouse_pct: Decimal
    handling_pct: Decimal


class TradeRouteParamsUpdate(BaseModel):
    fx_rate: Decimal | None = None
    fx_buffer_pct: Decimal | None = None
    freight_rate_per_kg: Decimal | None = Field(None, ge=0)
    freight_min_aed: Decimal | None = Field(None, ge=0)
    import_tariff_pct: Decimal | None = Field(None, ge=0, le=50)
    local_warehouse_pct: Decimal | None = Field(None, ge=0, le=20)
    handling_pct: Decimal | None = Field(None, ge=0, le=20)


# ── Channel Fee Params ────────────────────────────────────────────────


class ChannelFeeParamsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    route_id: UUID
    mt_discount_pct: Decimal
    commission_pct: Decimal
    vat_pct: Decimal
    advertising_pct: Decimal
    returns_pct: Decimal
    storage_multiplier: Decimal


class ChannelFeeParamsUpdate(BaseModel):
    mt_discount_pct: Decimal | None = Field(None, ge=0, le=50)
    commission_pct: Decimal | None = Field(None, ge=0, le=30)
    vat_pct: Decimal | None = Field(None, ge=0, le=30)
    advertising_pct: Decimal | None = Field(None, ge=0, le=30)
    returns_pct: Decimal | None = Field(None, ge=0, le=15)
    storage_multiplier: Decimal | None = Field(None, ge=0, le=5)


# ── Channel Scheme Params ─────────────────────────────────────────────


class ChannelSchemeParamsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    fulfillment_scheme: FulfillmentScheme
    scheme_label: str
    is_available: bool
    flat_supplement_aed: Decimal
    pct_surcharge: Decimal
    max_weight_kg: Decimal | None


# ── Channel Product Logistics ─────────────────────────────────────────


class ChannelProductLogisticsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_sku: str
    channel_id: UUID
    inbound_fee_aed: Decimal
    storage_fee_aed: Decimal
    fulfillment_fee_aed: Decimal
    default_scheme: FulfillmentScheme


class ChannelProductLogisticsUpsert(BaseModel):
    product_sku: str
    inbound_fee_aed: Decimal = Field(ge=0)
    storage_fee_aed: Decimal = Field(ge=0)
    fulfillment_fee_aed: Decimal = Field(ge=0)
    default_scheme: FulfillmentScheme = FulfillmentScheme.CANAL_FULL


# ── Margin Targets ────────────────────────────────────────────────────


class MarginTargetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    family_id: UUID
    family_name: str  # joined from families table
    selling_model: SellingModel
    margin_target_pct: Decimal


class MarginTargetUpsert(BaseModel):
    family_id: UUID
    selling_model: SellingModel = SellingModel.B2C
    margin_target_pct: Decimal = Field(ge=-10, le=80)


# ── Margin Overrides ──────────────────────────────────────────────────


class MarginOverrideRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    product_sku: str
    channel_id: UUID
    selling_model: SellingModel
    margin_override_pct: Decimal
    reason: str | None


class MarginOverrideUpsert(BaseModel):
    margin_override_pct: Decimal = Field(ge=-10, le=80)
    selling_model: SellingModel = SellingModel.B2C
    reason: str | None = None


# ── Catalog Import ────────────────────────────────────────────────────


class CatalogImportRow(BaseModel):
    sku: str
    pe_eur: Decimal = Field(gt=0)
    catalog_pvp_eur: Decimal = Field(gt=0)
    units_per_box: int = Field(ge=1)
    weight_kg: Decimal | None = Field(None, gt=0)
    ceiling_basis: CeilingBasis = CeilingBasis.CATALOG_PVP


class CatalogImportResult(BaseModel):
    total_rows: int
    upserted: int
    errors: list[dict]
    ceiling_preview: list[dict]


class LogisticsImportRow(BaseModel):
    sku: str
    inbound_fee_aed: Decimal = Field(ge=0)
    storage_fee_aed: Decimal = Field(ge=0)
    fulfillment_fee_aed: Decimal = Field(ge=0)
    default_scheme: FulfillmentScheme = FulfillmentScheme.CANAL_FULL


# ── Scenarios ─────────────────────────────────────────────────────────


class ScenarioRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    channel_id: UUID
    selling_model: SellingModel
    slot: str
    label: str | None


__all__ = [
    "CatalogImportResult",
    "CatalogImportRow",
    "ChannelFeeParamsRead",
    "ChannelFeeParamsUpdate",
    "ChannelProductLogisticsRead",
    "ChannelProductLogisticsUpsert",
    "ChannelSchemeParamsRead",
    "LogisticsImportRow",
    "MarginOverrideRead",
    "MarginOverrideUpsert",
    "MarginTargetRead",
    "MarginTargetUpsert",
    "ScenarioRead",
    "TradeRouteParamsRead",
    "TradeRouteParamsUpdate",
]
