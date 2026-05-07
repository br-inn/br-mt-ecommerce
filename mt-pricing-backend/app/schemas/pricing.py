"""Pydantic schemas para `prices`, `channels`, `fx_rates`, `costs`,
`exception_rules`, `price_approval_events`."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

from app.db.enums import ChannelState, PriceState

CHANNEL_CODE_REGEX = r"^[a-z0-9_]{2,64}$"
SCHEME_CODE_REGEX = r"^[A-Z][A-Z0-9_]{1,31}$"
CURRENCY_CODE_REGEX = r"^[A-Z]{3}$"

ChannelCodeStr = Annotated[
    str,
    StringConstraints(min_length=2, max_length=64, pattern=CHANNEL_CODE_REGEX),
]
SchemeCodeStr = Annotated[
    str,
    StringConstraints(min_length=2, max_length=32, pattern=SCHEME_CODE_REGEX),
]


# ---------------------------------------------------------------------------
# Channel
# ---------------------------------------------------------------------------
class ChannelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    name: str
    state: str
    schemes_supported: list[str] = Field(default_factory=list)
    state_history: list[dict[str, Any]] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class ChannelStateUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    state: str = Field(description="Nuevo estado")
    reason: str | None = Field(default=None, max_length=512)


# ---------------------------------------------------------------------------
# FX Rate
# ---------------------------------------------------------------------------
class FXRateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    from_currency: str
    to_currency: str
    rate: Decimal
    effective_from: datetime
    effective_to: datetime | None = None
    source: str | None = None
    created_at: datetime


class FXRateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_currency: str = Field(pattern=CURRENCY_CODE_REGEX, min_length=3, max_length=3)
    to_currency: str = Field(pattern=CURRENCY_CODE_REGEX, min_length=3, max_length=3)
    rate: Decimal = Field(gt=0)
    effective_from: datetime | None = None
    source: str | None = Field(default="manual", max_length=32)


# ---------------------------------------------------------------------------
# Pricing result (preview / simulate)
# ---------------------------------------------------------------------------
class PricingAlert(BaseModel):
    severity: str  # 'info' | 'warning' | 'critical'
    code: str
    message: str
    extra: dict[str, Any] | None = None


class PricingResultResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")
    amount: Decimal
    pvp_min: Decimal | None = None
    margin_pct: Decimal
    rule_applied: str
    formula: str
    breakdown: dict[str, Any] = Field(default_factory=dict)
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    fx_at: datetime | None = None
    has_velocity_premium: bool = False
    has_critical_alerts: bool = False
    has_warnings: bool = False
    cap_applied: bool = False
    floor_applied: bool = False


# ---------------------------------------------------------------------------
# Price (DB row)
# ---------------------------------------------------------------------------
class PriceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    product_sku: str
    channel_id: UUID
    scheme_code: str
    amount: Decimal
    pvp_min: Decimal | None = None
    margin_pct: Decimal
    currency: str
    rule_applied: str | None = None
    formula: str | None = None
    breakdown: dict[str, Any] = Field(default_factory=dict)
    alerts: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    proposed_by: UUID | None = None
    approved_by: UUID | None = None
    approved_at: datetime | None = None
    rejection_reason: str | None = None
    valid_from: datetime
    valid_to: datetime | None = None
    created_at: datetime
    updated_at: datetime


class PriceApprovalEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    price_id: UUID
    actor_id: UUID
    from_status: str
    to_status: str
    reason: str | None = None
    metadata_jsonb: dict[str, Any] = Field(default_factory=dict, alias="metadata_jsonb")
    created_at: datetime


class PriceDetailResponse(PriceResponse):
    """Price + history of approval events."""

    approval_events: list[PriceApprovalEventResponse] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Mutation requests
# ---------------------------------------------------------------------------
class PriceProposeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_sku: str = Field(min_length=1, max_length=128)
    channel_code: ChannelCodeStr
    scheme_code: SchemeCodeStr
    market: dict[str, Any] | None = None
    master_data: dict[str, Any] | None = None


class PriceApprovalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str | None = Field(default=None, max_length=2048)


class PriceRejectRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2048)


class PriceReviseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_amount: Decimal = Field(gt=0)
    reason: str = Field(min_length=1, max_length=2048)


class PriceBulkApproveRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    price_ids: list[UUID] = Field(min_length=1, max_length=500)
    reason: str | None = Field(default=None, max_length=2048)


class PricingCalculateRequest(BaseModel):
    """Preview sin persistencia — usa cost activo + master opcional."""

    model_config = ConfigDict(extra="forbid")
    product_sku: str = Field(min_length=1, max_length=128)
    channel_code: ChannelCodeStr
    scheme_code: SchemeCodeStr
    market: dict[str, Any] | None = None
    master_data: dict[str, Any] | None = None


class PricingSimulateRequest(BaseModel):
    """What-if simulator. `scenario_overrides` permite pisar cost/median/fx."""

    model_config = ConfigDict(extra="forbid")
    product_sku: str = Field(min_length=1, max_length=128)
    channel_code: ChannelCodeStr
    scheme_code: SchemeCodeStr
    scenario_overrides: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Exception rule (admin)
# ---------------------------------------------------------------------------
class ExceptionRuleResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    code: str
    description: str | None = None
    channel_id: UUID | None = None
    scheme_code: str | None = None
    margin_threshold_pct: Decimal | None = None
    fx_swing_threshold_pct: Decimal | None = None
    min_margin_pct: Decimal | None = None
    active: bool


__all__ = [
    "ChannelResponse",
    "ChannelStateUpdate",
    "ExceptionRuleResponse",
    "FXRateCreate",
    "FXRateResponse",
    "PriceApprovalEventResponse",
    "PriceApprovalRequest",
    "PriceBulkApproveRequest",
    "PriceDetailResponse",
    "PriceProposeRequest",
    "PriceRejectRequest",
    "PriceResponse",
    "PriceReviseRequest",
    "PricingAlert",
    "PricingCalculateRequest",
    "PricingResultResponse",
    "PricingSimulateRequest",
]
