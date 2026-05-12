"""Pydantic V2 schemas — Fase 4 documents.

Contrato HTTP para CRUD de documentos controlados (fichas técnicas,
manuales, declaraciones CE, certificados, catálogos) con versionado e idioma.
"""

from __future__ import annotations

from datetime import date, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enum
# ---------------------------------------------------------------------------
class DocumentType(StrEnum):
    FICHA_TECNICA = "ficha_tecnica"
    MANUAL = "manual"
    DECLARACION_CE = "declaracion_ce"
    CERTIFICADO = "certificado"
    CATALOGO = "catalogo"


# ---------------------------------------------------------------------------
# Create
# ---------------------------------------------------------------------------
class DocumentCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: DocumentType
    code: Annotated[str, Field(min_length=1, max_length=128)]
    version: Annotated[str, Field(min_length=1, max_length=64)]
    language: Annotated[str, Field(min_length=2, max_length=2)]
    asset_id: UUID
    issued_at: date | None = None

    @field_validator("language")
    @classmethod
    def _lang_lower(cls, v: str) -> str:
        return v.lower()


# ---------------------------------------------------------------------------
# Patch
# ---------------------------------------------------------------------------
class DocumentPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    type: DocumentType | None = None
    code: Annotated[str | None, Field(default=None, min_length=1, max_length=128)] = None
    version: Annotated[str | None, Field(default=None, min_length=1, max_length=64)] = None
    language: Annotated[str | None, Field(default=None, min_length=2, max_length=2)] = None
    asset_id: UUID | None = None
    issued_at: date | None = None

    @field_validator("language")
    @classmethod
    def _lang_lower(cls, v: str | None) -> str | None:
        return v.lower() if v is not None else None

    @model_validator(mode="after")
    def _at_least_one_field(self) -> DocumentPatch:
        if not self.model_dump(exclude_unset=True):
            raise ValueError("PATCH payload vacío — al menos un campo requerido.")
        return self


# ---------------------------------------------------------------------------
# Response
# ---------------------------------------------------------------------------
class DocumentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True, extra="ignore")

    id: UUID
    type: str
    code: str
    version: str
    language: str
    asset_id: UUID
    issued_at: date | None = None
    created_at: datetime
