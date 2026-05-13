"""Pydantic V2 schemas — EP-ERP-03 (Compras P2P)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Purchase Requisition
# ---------------------------------------------------------------------------

class PRCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    product_id: UUID | None = None
    qty: Decimal = Field(gt=0)
    uom: str = Field(default="UNIT", max_length=32)
    required_date: date | None = None
    cost_center_id: str | None = Field(default=None, max_length=64)
    suggested_vendor_id: UUID | None = None
    estimated_amount: Decimal | None = Field(default=None, ge=0)
    notes: str | None = None


class PROut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    pr_number: str
    requester_id: UUID
    product_id: UUID | None
    qty: Decimal
    uom: str
    required_date: date | None
    cost_center_id: str | None
    suggested_vendor_id: UUID | None
    estimated_amount: Decimal | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime


class PRSubmit(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PRReject(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: str = Field(min_length=1)


# ---------------------------------------------------------------------------
# Approval Decision
# ---------------------------------------------------------------------------

class ApprovalDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    document_id: UUID
    document_type: str
    approver_id: UUID
    action: str
    reason: str | None
    decided_at: datetime


# ---------------------------------------------------------------------------
# Approval Rule
# ---------------------------------------------------------------------------

class ApprovalRuleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    document_type: str = Field(default="purchase_requisition", max_length=64)
    min_amount: Decimal = Field(default=Decimal("0"), ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    category_id: str | None = Field(default=None, max_length=64)
    approver_role: str | None = Field(default=None, max_length=32)
    approver_user_id: UUID | None = None
    timeout_hours: int = Field(default=48, ge=0)
    priority: int = Field(default=0, ge=0)
    is_active: bool = True


class ApprovalRuleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    document_type: str
    min_amount: Decimal
    max_amount: Decimal | None
    category_id: str | None
    approver_role: str | None
    approver_user_id: UUID | None
    timeout_hours: int
    priority: int
    is_active: bool
    created_at: datetime


class ApprovalRuleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    min_amount: Decimal | None = Field(default=None, ge=0)
    max_amount: Decimal | None = Field(default=None, ge=0)
    category_id: str | None = None
    approver_role: str | None = Field(default=None, max_length=32)
    approver_user_id: UUID | None = None
    timeout_hours: int | None = Field(default=None, ge=0)
    priority: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Vendor Product Condition (PIR)
# ---------------------------------------------------------------------------

class VendorConditionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    vendor_id: str = Field(min_length=1, max_length=64)
    product_id: UUID
    price: Decimal = Field(ge=0)
    uom: str = Field(default="UNIT", max_length=32)
    moq: int = Field(default=1, ge=1)
    lead_time_days: int | None = Field(default=None, ge=0)
    valid_from: date | None = None
    valid_to: date | None = None
    currency: str = Field(default="AED", min_length=3, max_length=3)
    is_active: bool = True


class VendorConditionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    vendor_id: str
    product_id: UUID
    price: Decimal
    uom: str
    moq: int
    lead_time_days: int | None
    valid_from: date
    valid_to: date | None
    currency: str
    is_active: bool
    created_at: datetime


class VendorConditionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    price: Decimal | None = Field(default=None, ge=0)
    uom: str | None = Field(default=None, max_length=32)
    moq: int | None = Field(default=None, ge=1)
    lead_time_days: int | None = Field(default=None, ge=0)
    valid_to: date | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    is_active: bool | None = None
