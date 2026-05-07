"""Imports → datasheets PDF — API v1 (US-1A-06-04, Sprint 4).

Endpoints (paralelos a ``/imports/costs``):

- ``POST /imports/datasheets/preview`` — sube uno o varios PDFs y obtiene
  ``run_id`` con summary + orphan_files + orphan_skus + samples.
- ``POST /imports/datasheets/{run_id}/apply`` — confirma la asociación a
  productos vía ``ProductService.attach_datasheet``.
- ``GET  /imports/datasheets/{run_id}/status``.

RBAC: ``imports:write`` (TI Integración + admin). Comercial NO puede aplicar.

Nota: este router NO se registra automáticamente en ``app/api/routes/__init__.py``
para respetar el constraint del Sprint 4 — devolvemos un parche al final.
"""

from __future__ import annotations

from typing import Annotated, Any
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.imports_datasheets import (
    DatasheetsDiffSample,
    ImportDatasheetsApplyRequest,
    ImportDatasheetsPreviewResponse,
    ImportDatasheetsRunStatusResponse,
)
from app.services.importer.importer_service import (
    ImporterDomainError,
)
from app.services.importer_datasheets import (
    ImporterDatasheetsService,
    ProductServiceProtocol,
)

router = APIRouter(prefix="/imports/datasheets", tags=["imports", "imports:datasheets"])


def get_importer_datasheets_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImporterDatasheetsService:
    return ImporterDatasheetsService(session)


def get_product_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ProductServiceProtocol:
    """Resuelve el ProductService real cuando exista; lanza 503 mientras no."""
    try:  # pragma: no cover  — opt-in cuando aterrice
        from app.services.products.product_service import ProductService  # type: ignore

        return ProductService(session)  # type: ignore[return-value]
    except ImportError:
        return _PendingProductService()  # pragma: no cover


class _PendingProductService:  # pragma: no cover  — sólo si product_service no merge
    async def attach_datasheet(self, **kwargs: Any) -> Any:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "product_service_unavailable",
                "title": "ProductService.attach_datasheet aún no disponible.",
            },
        )


def _raise_domain(err: ImporterDomainError) -> None:
    raise HTTPException(
        status_code=err.status_code,
        detail={"code": err.code, "title": err.message},
    )


def _summary_to_samples(diffs: list[Any], limit: int = 50) -> list[DatasheetsDiffSample]:
    out: list[DatasheetsDiffSample] = []
    for d in diffs[:limit]:
        out.append(
            DatasheetsDiffSample(
                row_index=d.row_index,
                filename=d.filename,
                kind=d.kind,
                product_sku=d.product_sku,
                storage_path=d.storage_path,
                specs=d.specs.to_dict() if hasattr(d.specs, "to_dict") else dict(d.specs or {}),
                file_size_bytes=d.file_size_bytes,
            )
        )
    return out


@router.post(
    "/preview",
    response_model=ImportDatasheetsPreviewResponse,
    summary="Preview de PDFs datasheet — parsea filename + specs y reporta orphans",
    description=(
        "Sube uno o varios PDFs datasheet (MTFT_*/MTCE_*/MTMAN_*), parsea "
        "filename + specs (DN/PN/material/seal). Reporta orphan_files y "
        "orphan_skus. No persiste."
    ),
    operation_id="importDatasheetsPreview",
    responses={
        413: {"model": ProblemDetails, "description": "Archivo > 10 MB"},
        422: {"model": ProblemDetails},
    },
)
async def preview_datasheets_import(
    files: Annotated[list[UploadFile], File(description="PDFs datasheet (≤ 10 MB c/u)")],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    service: Annotated[ImporterDatasheetsService, Depends(get_importer_datasheets_service)],
) -> ImportDatasheetsPreviewResponse:
    if not files:
        raise HTTPException(
            status_code=422,
            detail={"code": "no_files", "title": "Debe subir al menos un PDF."},
        )
    payloads: list[tuple[str, bytes]] = []
    for f in files:
        if f.filename is None:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "import_missing_filename",
                    "title": "filename requerido",
                },
            )
        payloads.append((f.filename, await f.read()))

    try:
        state = await service.preview(files=payloads, actor=user)
    except ImporterDomainError as e:
        _raise_domain(e)
        raise  # pragma: no cover
    return ImportDatasheetsPreviewResponse(
        run_id=state.run_id,
        kind=state.kind,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        orphan_files=state.orphan_files,
        orphan_skus=state.orphan_skus,
        samples=_summary_to_samples(state.diffs, limit=20),
    )


@router.post(
    "/{run_id}/apply",
    response_model=ImportDatasheetsRunStatusResponse,
    summary="Aplica la asociación de datasheets a productos",
    description=(
        "Confirma el run y asocia los PDFs a sus productos vía "
        "`ProductService.attach_datasheet`. Sube los archivos a Supabase "
        "Storage `product-images`."
    ),
    operation_id="importDatasheetsApply",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Run en estado inválido"},
        503: {"model": ProblemDetails, "description": "ProductService no disponible"},
    },
)
async def apply_datasheets_import(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    service: Annotated[ImporterDatasheetsService, Depends(get_importer_datasheets_service)],
    product_service: Annotated[ProductServiceProtocol, Depends(get_product_service)],
    body: ImportDatasheetsApplyRequest | None = None,
) -> ImportDatasheetsRunStatusResponse:
    _ = body
    try:
        state = await service.apply(run_id, user, product_service=product_service)
    except ImporterDomainError as e:
        _raise_domain(e)
        raise  # pragma: no cover
    return ImportDatasheetsRunStatusResponse(
        run_id=state.run_id,
        kind=state.kind,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        orphan_files=state.orphan_files,
        orphan_skus=state.orphan_skus,
        apply=state.apply_result.to_dict() if state.apply_result else None,
        error=state.error,
    )


@router.get(
    "/{run_id}/status",
    response_model=ImportDatasheetsRunStatusResponse,
    summary="Estado del run de datasheets",
    description=(
        "Devuelve el estado in-memory del run de datasheets (preview_ready, "
        "applying, completed, completed_with_errors, failed)."
    ),
    operation_id="importDatasheetsGetStatus",
    responses={404: {"model": ProblemDetails}},
)
async def get_status(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
    service: Annotated[ImporterDatasheetsService, Depends(get_importer_datasheets_service)],
) -> ImportDatasheetsRunStatusResponse:
    try:
        state = service.get_status(run_id)
    except ImporterDomainError as e:
        _raise_domain(e)
        raise  # pragma: no cover
    return ImportDatasheetsRunStatusResponse(
        run_id=state.run_id,
        kind=state.kind,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        orphan_files=state.orphan_files,
        orphan_skus=state.orphan_skus,
        apply=state.apply_result.to_dict() if state.apply_result else None,
        error=state.error,
    )


__all__ = [
    "get_importer_datasheets_service",
    "get_product_service",
    "router",
]


# silence unused-warning in some lints
_ = (UUID, uuid4)
