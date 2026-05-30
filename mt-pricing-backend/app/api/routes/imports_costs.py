"""Imports → costs — API v1 routes (US-1A-06-02).

Endpoints (paralelos a ``/imports`` PIM):
- ``POST /imports/costs/preview``        — sube xlsx costos, devuelve diff + orphans.
- ``POST /imports/costs/{run_id}/apply`` — confirma y aplica vía CostService.create_cost.
- ``GET  /imports/costs/{run_id}/status``
- ``GET  /imports/costs/{run_id}/report?format=json|csv``

RBAC: ``imports:write`` (TI Integración + admin). Comercial NO puede aplicar.

DEPENDENCIA: el applier llama ``CostService.create_cost`` (US-1A-04-03 — Agent F).
Hasta que ese service exista, los integration tests E2E quedan
``@pytest.mark.skip`` y los unit tests del applier mockean el contrato.
"""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Response,
    UploadFile,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db_session, require_permissions
from app.db.models.user import User
from app.schemas.common import ProblemDetails
from app.schemas.imports_costs import (
    ImportCostsApplyRequest,
    ImportCostsPreviewResponse,
    ImportCostsRunStatusResponse,
)
from app.services.importer.importer_service import (
    ImporterDomainError,
    ImportHeaderMismatchError,
)
from app.services.importer_costs import ImporterCostsService
from app.services.importer_costs.applier import CostServiceProtocol

router = APIRouter(prefix="/imports/costs", tags=["imports", "imports:costs"])


def get_importer_costs_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> ImporterCostsService:
    return ImporterCostsService(session)


def get_cost_service(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> CostServiceProtocol:
    """Resuelve el ``CostService`` real (vigencia por rangos).

    Los unit tests del router mockean este dependency. El fallback
    ``_PendingCostService`` sólo aplica si el módulo no estuviera disponible.
    """
    try:
        from app.services.costs.cost_service import CostService

        return CostService(session)  # type: ignore[return-value]
    except ImportError:  # pragma: no cover — el service ya existe
        return _PendingCostService()


class _PendingCostService:  # pragma: no cover — sólo si Agent F no merge aún
    async def create_cost(self, **kwargs: Any) -> Any:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "costs_service_unavailable",
                "title": ("POST /costs (US-1A-04-03) aún no merged. Importer apply en holding."),
            },
        )


def _raise_domain(err: ImporterDomainError) -> None:
    extra: dict[str, Any] = {"code": err.code, "title": err.message}
    if isinstance(err, ImportHeaderMismatchError):
        extra["header_errors"] = err.header_errors
    raise HTTPException(status_code=err.status_code, detail=extra)


@router.post(
    "/preview",
    response_model=ImportCostsPreviewResponse,
    summary="Preview xlsx costos: parsea + diff vs costs activos + orphans report",
    description=(
        "Sube un xlsx de costos, parsea + valida headers + computa diff vs "
        "costs activos. No persiste — devuelve `run_id` que se confirma "
        "luego con `/apply`."
    ),
    operation_id="importCostsPreview",
    responses={
        413: {"model": ProblemDetails, "description": "Archivo demasiado grande"},
        422: {"model": ProblemDetails, "description": "Header mismatch o parse error"},
    },
)
async def preview_costs_import(
    file: Annotated[UploadFile, File(description="xlsx costos batch (≤ 50 MB)")],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    service: Annotated[ImporterCostsService, Depends(get_importer_costs_service)],
) -> ImportCostsPreviewResponse:
    if file.filename is None:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "import_missing_filename",
                "title": "filename requerido",
            },
        )
    file_bytes = await file.read()
    try:
        state = await service.preview(file_bytes=file_bytes, filename=file.filename, actor=user)
    except ImporterDomainError as e:
        _raise_domain(e)

    payload = service.report_json(state.run_id, sample_per_bucket=20)
    return ImportCostsPreviewResponse(
        run_id=state.run_id,
        kind=state.kind,
        filename=state.filename,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        orphans=state.orphans.to_dict(),
        samples=payload["samples"],
    )


@router.post(
    "/{run_id}/apply",
    response_model=ImportCostsRunStatusResponse,
    summary="Aplicar diffs (CREATE/UPDATE) vía CostService.create_cost",
    description=(
        "Confirma y aplica los diffs del run de import (CREATE/UPDATE) "
        "vía `CostService`. Idempotente — un run sólo se puede aplicar "
        "una vez."
    ),
    operation_id="importCostsApply",
    responses={
        404: {"model": ProblemDetails},
        409: {"model": ProblemDetails, "description": "Run en estado inválido"},
        503: {"model": ProblemDetails, "description": "CostService no disponible"},
    },
)
async def apply_costs_import(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    user: Annotated[User, Depends(require_permissions("imports:write"))],
    service: Annotated[ImporterCostsService, Depends(get_importer_costs_service)],
    cost_service: Annotated[CostServiceProtocol, Depends(get_cost_service)],
    body: ImportCostsApplyRequest | None = None,
) -> ImportCostsRunStatusResponse:
    _ = body  # body opcional reservado para flags futuras
    try:
        state = await service.apply(run_id, user, cost_service=cost_service)
    except ImporterDomainError as e:
        _raise_domain(e)
    payload = service.report_json(run_id, sample_per_bucket=0)
    return ImportCostsRunStatusResponse(
        run_id=state.run_id,
        kind=state.kind,
        filename=state.filename,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        orphans=state.orphans.to_dict(),
        apply=payload["apply"],
        error=state.error,
    )


@router.get(
    "/{run_id}/status",
    response_model=ImportCostsRunStatusResponse,
    summary="Estado actual del run de costos",
    description=(
        "Devuelve el estado in-memory del run de import (preview_ready, "
        "applying, completed, completed_with_errors, failed)."
    ),
    operation_id="importCostsGetStatus",
    responses={404: {"model": ProblemDetails}},
)
async def get_status(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
    service: Annotated[ImporterCostsService, Depends(get_importer_costs_service)],
) -> ImportCostsRunStatusResponse:
    try:
        state = service.get_status(run_id)
    except ImporterDomainError as e:
        _raise_domain(e)
    payload = service.report_json(run_id, sample_per_bucket=0)
    return ImportCostsRunStatusResponse(
        run_id=state.run_id,
        kind=state.kind,
        filename=state.filename,
        status=state.status,
        created_at=state.created_at,
        summary=state.summary,
        orphans=state.orphans.to_dict(),
        apply=payload["apply"],
        error=state.error,
    )


@router.get(
    "/{run_id}/report",
    summary="Report del run (JSON detallado o CSV)",
    description=(
        "Devuelve el report del run de import en formato JSON (samples + "
        "summary) o CSV (descargable). `format` query param controla."
    ),
    operation_id="importCostsGetReport",
    responses={404: {"model": ProblemDetails}},
)
async def get_report(
    run_id: Annotated[str, Path(min_length=1, max_length=64)],
    _user: Annotated[User, Depends(require_permissions("imports:read"))],
    service: Annotated[ImporterCostsService, Depends(get_importer_costs_service)],
    format: Annotated[str, Query(pattern=r"^(json|csv)$")] = "json",
    sample_per_bucket: Annotated[int, Query(ge=0, le=500)] = 50,
) -> Any:
    try:
        if format == "csv":
            csv_text = service.report_csv(run_id)
            return Response(
                content=csv_text,
                media_type="text/csv",
                headers={
                    "Content-Disposition": (
                        f'attachment; filename="costs_import_{run_id}_report.csv"'
                    )
                },
            )
        return service.report_json(run_id, sample_per_bucket=sample_per_bucket)
    except ImporterDomainError as e:
        _raise_domain(e)
