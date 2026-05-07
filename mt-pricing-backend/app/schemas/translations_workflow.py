"""Pydantic V2 schemas para el Translations Approval Workflow (US-1A-02-05).

Estos schemas viven en su propio módulo (no en `schemas/products.py`) para
mantener el dominio aislado y evitar imports cruzados con el agente que
mantiene `schemas/products.py`. Reusan el shape de `ProductTranslationResponse`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from typing import Annotated


# Estados expuestos por la state machine completa S3.
TranslationWorkflowStatus = Literal[
    "draft",
    "pending",  # legacy alias S1/S2
    "pending_review",
    "approved",
    "stale",
]


class TranslationRejectRequest(BaseModel):
    """Body para POST /products/{sku}/translations/{lang}/reject.

    `reason` es obligatorio (auditoría exige motivo).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: Annotated[
        str,
        StringConstraints(min_length=3, max_length=1024),
    ] = Field(description="Motivo del rechazo (mostrado al autor en el tab Auditoría).")


class TranslationMarkStaleRequest(BaseModel):
    """Body opcional para POST /products/{sku}/translations/mark-stale.

    Permite a TI/sistema disparar manualmente el efecto del trigger
    `mark_translations_stale_on_master_edit` (utilidad de soporte;
    el flujo normal lo dispara la BD).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    reason: Annotated[
        str,
        StringConstraints(min_length=3, max_length=128),
    ] = Field(
        default="master_en_changed",
        description="Etiqueta de staleness; persistida en `staleness_reason`.",
    )


class TranslationWorkflowResponse(BaseModel):
    """Response para todas las transiciones del workflow.

    Mismo shape que `ProductTranslationResponse` con `staleness_reason`/
    `rejection_reason` opcional para reflejar columnas nuevas (S3).
    """

    model_config = ConfigDict(from_attributes=True, extra="ignore")

    sku: str
    lang: str
    name: str | None = None
    description: str | None = None
    marketing_copy: str | None = None
    status: TranslationWorkflowStatus
    translated_by: UUID | None = None
    translated_at: datetime | None = None
    reviewed_by: UUID | None = None
    reviewed_at: datetime | None = None
    staleness_reason: str | None = None
    rejection_reason: str | None = None
    created_at: datetime
    updated_at: datetime


class TranslationMarkStaleResponse(BaseModel):
    """Response del endpoint mark-stale — lista de traducciones afectadas."""

    model_config = ConfigDict(extra="forbid")

    sku: str
    affected_count: int = Field(ge=0)
    affected: list[TranslationWorkflowResponse] = Field(default_factory=list)


__all__ = [
    "TranslationMarkStaleRequest",
    "TranslationMarkStaleResponse",
    "TranslationRejectRequest",
    "TranslationWorkflowResponse",
    "TranslationWorkflowStatus",
]
