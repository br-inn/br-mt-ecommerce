"""Translations approval workflow — API v1 routes (US-1A-02-05).

Endpoints añadidos en Sprint 3:

- ``POST /api/v1/products/{sku}/translations/{lang}/request-review``
- ``POST /api/v1/products/{sku}/translations/{lang}/reject``  (con reason obligatorio)
- ``POST /api/v1/products/{sku}/translations/mark-stale``     (utilidad de soporte —
  el flujo principal lo dispara el trigger DB cuando cambia el master EN)

Nota: el endpoint clásico ``POST .../approve`` sigue viviendo en
``app.api.routes.products`` para minimizar el blast-radius del agente. Esta
ruta complementa el contrato sin tocar archivos críticos.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.translations_workflow import (
    TranslationMarkStaleRequest,
    TranslationMarkStaleResponse,
    TranslationRejectRequest,
    TranslationWorkflowResponse,
)
from app.services.products.product_service import ProductDomainError
from app.services.products.translation_workflow import (
    TranslationWorkflowService,
)

router = APIRouter(prefix="/products", tags=["products", "translations-workflow"])


# ---------------------------------------------------------------------------
# DI
# ---------------------------------------------------------------------------
def get_translation_workflow_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> TranslationWorkflowService:
    return TranslationWorkflowService(session)


def _raise_domain(err: ProductDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------
@router.post(
    "/{sku}/translations/{lang}/request-review",
    response_model=TranslationWorkflowResponse,
    summary="Marcar traducción como `pending_review` (autor pide revisión).",
    responses={
        404: {"model": ProblemDetails, "description": "SKU/translation no encontrado"},
        409: {"model": ProblemDetails, "description": "Transición inválida"},
    },
)
async def request_review(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    lang: Annotated[str, Path(pattern=r"^(es|ar)$")],
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[
        TranslationWorkflowService, Depends(get_translation_workflow_service)
    ],
) -> TranslationWorkflowResponse:
    try:
        row = await service.request_review(sku, lang, user)
    except ProductDomainError as e:
        _raise_domain(e)
    return TranslationWorkflowResponse.model_validate(row)


@router.post(
    "/{sku}/translations/{lang}/reject",
    response_model=TranslationWorkflowResponse,
    summary="Rechazar traducción `pending_review` con motivo (vuelve a `draft`).",
    responses={
        403: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Transición inválida"},
        422: {"model": ProblemDetails, "description": "Reason requerido"},
    },
)
async def reject_translation(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    lang: Annotated[str, Path(pattern=r"^(es|ar)$")],
    payload: TranslationRejectRequest,
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[
        TranslationWorkflowService, Depends(get_translation_workflow_service)
    ],
) -> TranslationWorkflowResponse:
    try:
        row = await service.reject(sku, lang, user, reason=payload.reason)
    except ProductDomainError as e:
        _raise_domain(e)
    return TranslationWorkflowResponse.model_validate(row)


@router.post(
    "/{sku}/translations/mark-stale",
    response_model=TranslationMarkStaleResponse,
    summary=(
        "Marcar traducciones aprobadas no-EN como `stale` "
        "(replica el efecto del trigger DB; pensado para soporte/TI)."
    ),
    responses={404: {"model": ProblemDetails}},
)
async def mark_stale(
    sku: Annotated[str, Path(min_length=1, max_length=64)],
    user: Annotated[User, Depends(require_permissions("products:write"))],
    service: Annotated[
        TranslationWorkflowService, Depends(get_translation_workflow_service)
    ],
    payload: TranslationMarkStaleRequest | None = None,
) -> TranslationMarkStaleResponse:
    reason = payload.reason if payload else "master_en_changed"
    try:
        affected = await service.mark_stale_for_master_edit(
            sku, user, reason=reason
        )
    except ProductDomainError as e:
        _raise_domain(e)
    return TranslationMarkStaleResponse(
        sku=sku,
        affected_count=len(affected),
        affected=[TranslationWorkflowResponse.model_validate(r) for r in affected],
    )
