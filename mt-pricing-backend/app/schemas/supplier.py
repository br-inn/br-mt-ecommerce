"""Pydantic schemas para `suppliers` — US-1A-03-02.

Patrones:
- ``code`` PK string (TRIM mayúsculas, regex similar al SKU).
- ``contract_currency`` ISO-4217 3 letras (validado por FK a ``currencies``).
- Soft-delete via ``active=false``; no se expone hard delete (BR VAT-compliance).
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Annotated

from pydantic import (
    BaseModel,
    ConfigDict,
    EmailStr,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)


SUPPLIER_CODE_REGEX = r"^[A-Z0-9][A-Z0-9_\-]{1,63}$"
CURRENCY_CODE_REGEX = r"^[A-Z]{3}$"

SupplierCodeStr = Annotated[
    str,
    StringConstraints(
        min_length=2, max_length=64, pattern=SUPPLIER_CODE_REGEX, strip_whitespace=True
    ),
]


class SupplierBase(BaseModel):
    """Campos editables — heredados por Create/Update."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=256)
    contact_email: EmailStr | None = Field(default=None)
    contact_phone: str | None = Field(default=None, max_length=64)
    contract_currency: str = Field(
        min_length=3, max_length=3, pattern=CURRENCY_CODE_REGEX
    )
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    payment_terms: str | None = Field(default=None, max_length=256)
    notes: str | None = Field(default=None, max_length=4096)
    active: bool = True

    @field_validator("contract_currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class SupplierCreate(SupplierBase):
    """POST /suppliers — requiere ``code`` (PK)."""

    code: SupplierCodeStr

    @field_validator("code")
    @classmethod
    def _normalize_code(cls, v: str) -> str:
        v = v.strip().upper()
        if not re.match(SUPPLIER_CODE_REGEX, v):
            raise ValueError(f"code inválido: {v}")
        return v


class SupplierUpdate(BaseModel):
    """PUT /suppliers/{code} — full update; ``code`` es inmutable (PK)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=256)
    contact_email: EmailStr | None = Field(default=None)
    contact_phone: str | None = Field(default=None, max_length=64)
    contract_currency: str = Field(
        min_length=3, max_length=3, pattern=CURRENCY_CODE_REGEX
    )
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    payment_terms: str | None = Field(default=None, max_length=256)
    notes: str | None = Field(default=None, max_length=4096)
    active: bool = True

    @field_validator("contract_currency")
    @classmethod
    def _upper(cls, v: str) -> str:
        return v.upper()


class SupplierPatch(BaseModel):
    """PATCH parcial — al menos un campo requerido."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str | None = Field(default=None, min_length=1, max_length=256)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=64)
    contract_currency: str | None = Field(
        default=None, min_length=3, max_length=3, pattern=CURRENCY_CODE_REGEX
    )
    lead_time_days: int | None = Field(default=None, ge=0, le=3650)
    payment_terms: str | None = Field(default=None, max_length=256)
    notes: str | None = Field(default=None, max_length=4096)
    active: bool | None = None

    @field_validator("contract_currency")
    @classmethod
    def _upper(cls, v: str | None) -> str | None:
        if v is None:
            return v
        return v.upper()

    @model_validator(mode="after")
    def _at_least_one_field(self) -> "SupplierPatch":
        if not self.model_dump(exclude_unset=True):
            raise ValueError("PATCH payload vacío — al menos un campo requerido.")
        return self


class SupplierResponse(BaseModel):
    """Response estándar para listados / mutaciones."""

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    code: str
    name: str
    contact_email: str | None = None
    contact_phone: str | None = None
    contract_currency: str
    lead_time_days: int | None = None
    payment_terms: str | None = None
    notes: str | None = None
    active: bool
    created_at: datetime
    updated_at: datetime
