"""Documents API — Fase 4 versioned controlled documents (PDF §11).

Endpoints:
- GET    /api/v1/documents?type=...&language=...      (lista filtrable)
- GET    /api/v1/documents/{document_id}               (single)
- POST   /api/v1/admin/documents                       (crea)
- PATCH  /api/v1/admin/documents/{document_id}         (parche)
- DELETE /api/v1/admin/documents/{document_id}         (borra, 204)
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.documents import (
    DocumentCreate,
    DocumentPatch,
    DocumentResponse,
    DocumentType,
)
from app.services.documents.document_service import (
    DocumentDomainError,
    DocumentService,
)

router = APIRouter(tags=["documents"])
admin_router = APIRouter(prefix="/admin", tags=["admin:documents"])


def get_document_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> DocumentService:
    return DocumentService(session)


def _raise_domain(err: DocumentDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"type": "about:blank", "title": err.code, "detail": err.message},
    )


# ---------------------------------------------------------------------------
# Public: list + get
# ---------------------------------------------------------------------------
@router.get(
    "/documents",
    response_model=list[DocumentResponse],
    summary="Lista documentos controlados (filtros opcionales)",
)
async def list_documents(
    type: Annotated[DocumentType | None, Query()] = None,
    language: Annotated[str | None, Query(min_length=2, max_length=2)] = None,
    _user: User = Depends(require_permissions("products:read")),
    service: DocumentService = Depends(get_document_service),
) -> list[DocumentResponse]:
    rows = await service.list_documents(
        type_=type.value if type is not None else None,
        language=language,
    )
    return [DocumentResponse.model_validate(r) for r in rows]


@router.get(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="Obtiene un documento por id",
    responses={404: {"model": ProblemDetails}},
)
async def get_document(
    document_id: UUID,
    _user: User = Depends(require_permissions("products:read")),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        row = await service.get_document(document_id)
    except DocumentDomainError as e:
        _raise_domain(e)
    return DocumentResponse.model_validate(row)


# ---------------------------------------------------------------------------
# Admin: create / patch / delete
# ---------------------------------------------------------------------------
@admin_router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="[Admin] Crea un documento controlado",
    responses={
        409: {"model": ProblemDetails},
        404: {"model": ProblemDetails},
    },
)
async def admin_create_document(
    data: DocumentCreate,
    _user: User = Depends(require_permissions("admin:documents")),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    try:
        row = await service.create(
            {
                "type": data.type.value,
                "code": data.code,
                "version": data.version,
                "language": data.language,
                "asset_id": data.asset_id,
                "issued_at": data.issued_at,
            }
        )
    except DocumentDomainError as e:
        _raise_domain(e)
    return DocumentResponse.model_validate(row)


@admin_router.patch(
    "/documents/{document_id}",
    response_model=DocumentResponse,
    summary="[Admin] Parchea un documento",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails},
    },
)
async def admin_patch_document(
    document_id: UUID,
    data: DocumentPatch,
    _user: User = Depends(require_permissions("admin:documents")),
    service: DocumentService = Depends(get_document_service),
) -> DocumentResponse:
    patch_payload = data.model_dump(exclude_unset=True)
    # Normalizar type enum a string si presente.
    if "type" in patch_payload and patch_payload["type"] is not None:
        patch_payload["type"] = (
            patch_payload["type"].value
            if hasattr(patch_payload["type"], "value")
            else patch_payload["type"]
        )
    try:
        row = await service.patch(document_id, patch_payload)
    except DocumentDomainError as e:
        _raise_domain(e)
    return DocumentResponse.model_validate(row)


@admin_router.delete(
    "/documents/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="[Admin] Elimina un documento",
    responses={404: {"model": ProblemDetails}},
)
async def admin_delete_document(
    document_id: UUID,
    _user: User = Depends(require_permissions("admin:documents")),
    service: DocumentService = Depends(get_document_service),
):
    try:
        await service.delete(document_id)
    except DocumentDomainError as e:
        _raise_domain(e)
