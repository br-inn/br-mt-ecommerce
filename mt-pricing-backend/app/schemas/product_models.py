"""Pydantic v2 schemas para la jerarquía product_models (mig 126-127)."""
from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class ProductModelResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    series_id: UUID | None = None
    code: str
    color_label: str | None = None
    connection_type: str | None = None
    thread_standard: str | None = None
    active: bool
    variant_of_id: UUID | None = None
    created_at: datetime
    updated_at: datetime


class CertificateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    model_id: UUID | None = None
    cert_number: str
    issuer: str | None = None
    issued_at: date | None = None
    expires_at: date | None = None
    status: str
    signatory_name: str | None = None
    signatory_role: str | None = None
    notes: str | None = None
    created_at: datetime
    updated_at: datetime


class ModelFlowDataResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    model_id: UUID
    dn_mm: int
    kv: float | None = None
    cv: float | None = None
    mesh_mm: float | None = None
